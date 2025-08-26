# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from datetime import datetime, date, time, timedelta
from collections import defaultdict
import pytz
import logging
class AttendanceReportWizard(models.TransientModel):
    _name = "attendance.report.wizard"
    _description = "Asistencias - Reporte PDF (desde daily.attendance)"

    # --- NUEVO: default a 'Tlajomulco'
    @api.model
    def _default_work_location_id(self):
        # Busca por nombre (insensible a mayúsculas) en la compañía del usuario si aplica
        domain = [('name', 'ilike', 'Tlajomulco')]
        # Si tu modelo tiene company_id y quieres acotar:
        if 'company_id' in self.env['hr.work.location']._fields:
            domain = ['|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)] + domain
        loc = self.env['hr.work.location'].search(domain, limit=1)
        return loc.id or False

    date_from = fields.Datetime(required=True, default=lambda s: fields.Datetime.now() - timedelta(days=7))
    date_to   = fields.Datetime(required=True,   default=lambda s: fields.Datetime.now())

    work_location_id = fields.Many2one(
        "hr.work.location",
        string="Sucursal",
        default=_default_work_location_id,   # <<< AQUÍ
        help="Filtra empleados por su ubicación de trabajo."
    )

    employee_ids = fields.Many2many(
        "hr.employee",
        domain="[('active','=',True)] if not work_location_id else [('active','=',True), ('work_location_id','=', work_location_id)]",
        help="Si dejas vacío, se incluirán todos los empleados (o los de la sucursal seleccionada)."
    )

    include_signature = fields.Boolean(default=True)
    cards_per_page = fields.Selection([('2','2 por hoja'), ('3','3 por hoja')], default='2', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Si aún no hay sucursal seteada por contexto u otra lógica, aplica Tlajomulco
        if not res.get('work_location_id'):
            wl = self._default_work_location_id()
            if wl:
                res['work_location_id'] = wl

        # Prefill cuando se llama desde la lista Daily Attendance (tu lógica existente)
        ctx = self.env.context or {}
        if ctx.get('active_model') == 'daily.attendance' and ctx.get('active_ids'):
            recs = self.env['daily.attendance'].browse(ctx['active_ids'])
            tz = pytz.timezone(self.env.user.tz or 'UTC')
            tmin, tmax, emps = [], [], set()
            for r in recs:
                if r.punching_time:
                    tmin.append(r.punching_time); tmax.append(r.punching_time)
                elif r.punching_day:
                    start = tz.localize(datetime.combine(r.punching_day, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
                    end   = tz.localize(datetime.combine(r.punching_day, time.max)).astimezone(pytz.utc).replace(tzinfo=None)
                    tmin.append(start); tmax.append(end)
                if r.employee_id:
                    emps.add(r.employee_id.id)
            if tmin and tmax:
                res['date_from'] = min(tmin)
                res['date_to']   = max(tmax)
            if emps:
                res['employee_ids'] = [(6, 0, list(emps))]
        return res

    @api.onchange('work_location_id')
    def _onchange_work_location_id(self):
        if self.work_location_id and self.employee_ids:
            self.employee_ids = [(6, 0, self.employee_ids.filtered(
                lambda e: e.work_location_id == self.work_location_id
            ).ids)]


    # ----------------- DATASET SOLO DESDE daily.attendance -----------------
    def _fetch_dataset(self):
        """Obtiene dataset de asistencias, normalizado a la TZ del usuario."""
        self.ensure_one()
        tz = pytz.timezone(self.env.user.tz or 'UTC')

        # Rango
        dfrom = fields.Datetime.from_string(self.date_from)
        dto   = fields.Datetime.from_string(self.date_to)
        if dfrom > dto:
            dfrom, dto = dto, dfrom

        # Convertir límites a UTC "naive" para SQL (timestamp without tz en UTC)
        dfrom_utc = dfrom.astimezone(pytz.UTC).replace(tzinfo=None) if dfrom.tzinfo else dfrom
        dto_utc   = dto.astimezone(pytz.UTC).replace(tzinfo=None)   if dto.tzinfo   else dto

        # Empleados
        emp_domain = [('active', '=', True)]
        if self.work_location_id:
            emp_domain.append(('work_location_id', '=', self.work_location_id.id))

        employees = self.employee_ids or self.env['hr.employee'].search(
            emp_domain, order='work_location_id,name'
        )
        emp_ids = list(set(employees.ids)) or [-1]

        # Traer logs crudos
        query = """
            SELECT 
                id,
                employee_id,
                punching_day,
                address_id,
                attendance_type,
                punching_time,
                punch_type
            FROM daily_attendance
            WHERE punching_time BETWEEN %s AND %s
            AND employee_id = ANY(%s)
            ORDER BY employee_id, punching_time
        """
        self.env.cr.execute(query, (dfrom_utc, dto_utc, emp_ids))
        recs = self.env.cr.dictfetchall()

        # --- Normalizador de tipo de marca --------------------------------------
        IN_CODES        = {'0', '5', 0, 5}
        OUT_CODES       = {'1', '4', 1, 4}
        BREAK_HINTS_OUT = {'break out', 'lunch out', 'break start', 'meal out'}
        BREAK_HINTS_IN  = {'break in',  'lunch in',  'break end',   'meal in'}

        def _classify(v_att, v_punch):
            """
            Devuelve: 'in' | 'out' | 'lunch_out' | 'lunch_in'
            Acepta códigos numéricos (0/5=in, 1/4=out) y textos variados
            (Check In/Out, Overtime In/Out, Duty On/Off, Break/Lunch).
            """
            val = v_punch if v_punch not in (None, '') else v_att
            if val is None:
                return 'in'

            s = str(val).strip()
            sl = s.lower()

            # Hints de break/comida primero
            if any(h in sl for h in BREAK_HINTS_OUT):
                return 'lunch_out'
            if any(h in sl for h in BREAK_HINTS_IN):
                return 'lunch_in'

            # Códigos numéricos
            if s in IN_CODES:
                return 'in'
            if s in OUT_CODES:
                return 'out'

            # Textos comunes
            if 'check in' in sl or 'overtime in' in sl or 'duty on' in sl or sl == 'in':
                return 'in'
            if 'check out' in sl or 'overtime out' in sl or 'duty off' in sl or sl == 'out':
                return 'out'

            # Por defecto, entrada
            return 'in'
        # ------------------------------------------------------------------------

        # Día-list en TZ del usuario (INCLUSIVO)
        start_local = (pytz.utc.localize(dfrom) if dfrom.tzinfo is None else dfrom.astimezone(pytz.UTC)).astimezone(tz)
        end_local   = (pytz.utc.localize(dto)   if dto.tzinfo   is None else dto.astimezone(pytz.UTC)).astimezone(tz)

        day_list = []
        day = start_local.date()
        end_day = end_local.date()
        while day <= end_day:
            day_list.append(day)
            day += timedelta(days=1)

        # Agrupar por empleado/día con tiempos ya en TZ del usuario
        from collections import defaultdict as dd
        per_emp_day = dd(lambda: dd(list))

        for r in recs:
            # Filtro suave por sucursal (si evento trae address y no coincide, omitir)
            if self.work_location_id and r.get('address_id') and r['address_id'] != self.work_location_id.id:
                continue

            when = r.get('punching_time')
            if not when:
                continue

            # UTC -> TZ del usuario
            if when.tzinfo is None:
                localized_time = pytz.utc.localize(when).astimezone(tz)
            else:
                localized_time = when.astimezone(tz)

            punch = _classify(r.get('attendance_type'), r.get('punch_type'))

            per_emp_day[r['employee_id']][localized_time.date()].append(
                (localized_time, punch, localized_time.hour, localized_time.minute)
            )

        # Ordenar marcas por hora
        for emp_id, days in per_emp_day.items():
            for d in days:
                days[d].sort(key=lambda tup: tup[0])

        # ------------------ RESUMEN POR DÍA (incluye COMIDA) --------------------
        LUNCH_MIN = timedelta(minutes=30)   # mínimo para inferir comida
        LUNCH_MAX = timedelta(hours=3)      # máximo razonable para comida

        def _hhmm(total_secs):
            total_secs = max(0, int(total_secs))
            h = total_secs // 3600
            m = (total_secs % 3600) // 60
            return f"{h:02d}:{m:02d}"

        def _summarize_day(sorted_logs):
            """
            Recibe lista ordenada: [(dt, 'in'|'out'|'lunch_out'|'lunch_in', h, m), ...]
            Devuelve dict con: first_in, lunch_out, lunch_in, last_out, work_str, lunch_str
            """
            if not sorted_logs:
                return {
                    'first_in': None, 'last_out': None, 'lunch_out': None, 'lunch_in': None,
                    'work_secs': 0, 'lunch_secs': 0,
                    'first_in_s': '00:00', 'last_out_s': '00:00',
                    'lunch_out_s': '00:00', 'lunch_in_s': '00:00',
                    'work_str': '00:00', 'lunch_str': '00:00',
                }

            # primeras/últimas marcas
            first_in = next((dt for dt, p, *_ in sorted_logs if p == 'in'), None)
            last_out = next((dt for dt, p, *_ in reversed(sorted_logs) if p == 'out'), None)

            # comida explícita (primera pareja)
            lunch_out = next((dt for dt, p, *_ in sorted_logs if p == 'lunch_out'), None)
            lunch_in  = next((dt for dt, p, *_ in sorted_logs if p == 'lunch_in' and (not lunch_out or dt >= lunch_out)), None)

            # si no hay explícita, inferir con el mayor hueco entre first_in y last_out
            if (not lunch_out or not lunch_in) and first_in and last_out and last_out > first_in:
                times = [dt for (dt, _, *_ ) in sorted_logs if first_in <= dt <= last_out]
                max_gap = timedelta(0); s=None; e=None
                for a, b in zip(times, times[1:]):
                    gap = b - a
                    if gap > max_gap:
                        max_gap = gap; s = a; e = b
                if s and e and LUNCH_MIN <= max_gap <= LUNCH_MAX:
                    lunch_out, lunch_in = s, e

            # sumar horas por tramos (cerrando en lunch y reabriendo después)
            work_secs = 0
            open_in = None
            for dt, p, *_ in sorted_logs:
                if p == 'in' and open_in is None:
                    open_in = dt
                elif p == 'out' and open_in:
                    work_secs += int((dt - open_in).total_seconds())
                    open_in = None
                elif p == 'lunch_out' and open_in:
                    work_secs += int((dt - open_in).total_seconds())
                    open_in = None
                elif p == 'lunch_in' and open_in is None:
                    open_in = dt
            if open_in and last_out and last_out > open_in:
                work_secs += int((last_out - open_in).total_seconds())

            lunch_secs = 0
            if lunch_out and lunch_in and lunch_in > lunch_out:
                lunch_secs = int((lunch_in - lunch_out).total_seconds())

            fmt = lambda dt: dt and dt.strftime('%H:%M') or '00:00'
            return {
                'first_in': first_in,
                'last_out': last_out,
                'lunch_out': lunch_out,
                'lunch_in': lunch_in,
                'work_secs': work_secs,
                'lunch_secs': lunch_secs,
                'first_in_s': fmt(first_in),
                'last_out_s': fmt(last_out),
                'lunch_out_s': fmt(lunch_out),
                'lunch_in_s': fmt(lunch_in),
                'work_str': _hhmm(work_secs),
                'lunch_str': _hhmm(lunch_secs),
            }

        per_emp_day_summary = dd(dict)
        for emp in employees:
            emp_days = per_emp_day.get(emp.id, {})
            for d in day_list:
                per_emp_day_summary[emp.id][d] = _summarize_day(emp_days.get(d, []))
        # ------------------------------------------------------------------------

        # (Opcional) Log de diagnóstico: cuántas marcas por empleado
        _logger = logging.getLogger(__name__)
        for emp in employees:
            total_marks = sum(len(per_emp_day.get(emp.id, {}).get(d, [])) for d in day_list)
            _logger.debug("ATTN %s (%s): %s marcas en rango", emp.name, emp.id, total_marks)

        return {
            'employees': employees,
            'day_list': day_list,
            'per_emp_day': per_emp_day,                     # conserva marcas detalladas
            'per_emp_day_summary': per_emp_day_summary,     # NUEVO: resumen para pintar comida
            'dfrom': dfrom,
            'dto': dto,
            'tz': self.env.user.tz or 'UTC',
            'include_signature': self.include_signature,
        }