from odoo import api, models, fields, _
import logging
_logger = logging.getLogger('custom_reports_mooch.snapshot')
from datetime import datetime, date, time, timedelta
from collections import defaultdict
import pytz
import logging
from odoo.exceptions import UserError
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
        # Si prefieres mantener el dominio dinámico aquí también:
        domain="[('active','=',True), ('is_administrative','=',False)] if not work_location_id "
            "else [('active','=',True), ('is_administrative','=',False), ('work_location_id','=', work_location_id)]",
        help="Si dejas vacío, se incluirán solo empleados operativos (o los de la sucursal seleccionada)."
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

    def adjust_crossed_dates(self, events, tz):
        """
        Ajusta eventos que cruzan medianoche y empareja entradas con salidas correctamente.
        """
        adjusted_events = []

        for event_time, event_type, hour, minute in events:
            # Si el evento es entre medianoche y 6 AM, asignar al día anterior
            if 0 <= hour < 6:
                adjusted_date = event_time.date() - timedelta(days=1)
                adjusted_time = datetime.combine(adjusted_date, event_time.time())
                adjusted_events.append((adjusted_time, event_type, hour, minute))
            else:
                adjusted_events.append((event_time, event_type, hour, minute))

        return adjusted_events

    def group_events_by_workday(self, events_by_day):
        """
        Reagrupa eventos por día de trabajo, considerando turnos que cruzan medianoche.
        """
        from collections import defaultdict

        workday_events = defaultdict(list)

        for date_key, events in events_by_day.items():
            for event_time, event_type, hour, minute in events:
                # Para eventos de salida después de medianoche, usar fecha del día anterior
                if event_type == 'out' and 0 <= hour < 6:
                    workday_date = event_time.date() - timedelta(days=1)
                else:
                    workday_date = event_time.date()

                workday_events[workday_date].append((event_time, event_type, hour, minute))

        return workday_events
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
        emp_domain = [('active', '=', True), ('is_administrative', '=', False)]
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

        print("=== DATOS CRUDOS DE LA BASE DE DATOS ===")
        for r in recs:
            print(f"EMP: {r['employee_id']}, TIME: {r['punching_time']}, ATT_TYPE: {r['attendance_type']}, PUNCH_TYPE: {r['punch_type']}")
        print("========================================")
        # --- Normalizador de tipo de marca --------------------------------------
        def _classify(v_att, v_punch):
            """
            Devuelve: 'in' | 'out' | 'lunch_out' | 'lunch_in'
            - Basado en códigos numéricos del sistema
            """
            # Priorizar punch_type sobre attendance_type
            val = v_punch if v_punch not in (None, '') else v_att
            if val is None:
                return 'in'

            # Convertir a string y limpiar
            s = str(val).strip()
            sl = s.lower()

            print(f"DEBUG _classify: v_att='{v_att}', v_punch='{v_punch}', s='{s}'")

            # Mapeo CORREGIDO de códigos numéricos específicos del reloj
            # Basado en los datos que vimos:
            # 0 = Entrada (in)
            # 1 = Salida (out)
            # 4 = Inicio comida (lunch_out) - Overtime In
            # 5 = Fin comida (lunch_in) - Overtime Out
            if s == '0':
                print("DEBUG: Código 0 detectado como entrada")
                return 'in'
            elif s == '1':
                print("DEBUG: Código 1 detectado como salida")
                return 'out'
            elif s == '4':
                print("DEBUG: Código 4 detectado como lunch_out (Inicio comida)")
                return 'lunch_out'
            elif s == '5':
                print("DEBUG: Código 5 detectado como lunch_in (Fin comida)")
                return 'lunch_in'

            # Textos como fallback
            if any(keyword in sl for keyword in ['in', 'check in', 'checkin', 'entrada', 'on', 'duty on']):
                print("DEBUG: Entrada detectada por texto")
                return 'in'
            if any(keyword in sl for keyword in ['out', 'check out', 'checkout', 'salida', 'off', 'duty off']):
                print("DEBUG: Salida detectada por texto")
                return 'out'

            print("DEBUG: Por defecto, asumiendo entrada")
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

        # En la sección donde se procesan los eventos, agregar:
        for r in recs:
            when = r.get('punching_time')
            print(f"UTC: {when} - ATT_TYPE: {r['attendance_type']} - PUNCH_TYPE: {r['punch_type']}")

            # UTC -> TZ del usuario
            if when.tzinfo is None:
                localized_time = pytz.utc.localize(when).astimezone(tz)
            else:
                localized_time = when.astimezone(tz)

            print(f"LOCAL: {localized_time}")

            punch = _classify(r.get('attendance_type'), r.get('punch_type'))

            per_emp_day[r['employee_id']][localized_time.date()].append(
                (localized_time, punch, localized_time.hour, localized_time.minute)
            )

        # ===== NUEVO: AJUSTAR FECHAS CRUZADAS =====
        for emp_id, days in per_emp_day.items():
            # Primero ajustar fechas cruzadas
            adjusted_days = {}
            for day_date, events in days.items():
                adjusted_events = self.adjust_crossed_dates(events, tz)
                for event_time, event_type, hour, minute in adjusted_events:
                    adjusted_date = event_time.date()
                    if adjusted_date not in adjusted_days:
                        adjusted_days[adjusted_date] = []
                    adjusted_days[adjusted_date].append((event_time, event_type, hour, minute))

            # Luego reagrupar por día de trabajo
            workday_events = self.group_events_by_workday(adjusted_days)

            # Reemplazar los días originales con los días de trabajo
            per_emp_day[emp_id] = workday_events

        # Ordenar marcas por hora
        for emp_id, days in per_emp_day.items():
            for d in days:
                days[d].sort(key=lambda tup: tup[0])

        # ------------------ RESUMEN POR DÍA (incluye COMIDA) --------------------
        LUNCH_MIN = timedelta(minutes=30)   # mínimo para inferir comida
        LUNCH_MAX = timedelta(hours=2)      # máximo razonable para comida

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
            'cards_per_page': 4,
        }

    def action_print_pdf(self):
        self.ensure_one()
        ds = self._fetch_dataset()              # <- ESTE es el dataset “verdadero”
        return self.env.ref('custom_reports_mooch.action_attendance_pdf').report_action(
            self, data={'form': ds}
        )

    def action_save_snapshot(self):
        # Log de entrada
        _logger.info("SNAP_BTN: click -> self.ids=%s context=%s", self.ids, self.env.context)

        # ¿El registro sigue vivo?
        rec = self[:1].exists()
        _logger.info("SNAP_BTN: exists.ids=%s", rec.ids if rec else [])

        if not rec:
            # loguea lo que el cliente envió (a veces hay un res_id viejo en params)
            _logger.error("SNAP_BTN: wizard ya no existe; params=%s", self.env.context.get('params'))
            raise UserError(_("Este asistente ya no existe (expiró/limpieza). Vuelve a abrirlo y reintenta."))

        # Loguear valores clave del wizard (sin saturar logs)
        safe_fields = ['date_from','date_to','employee_ids','work_location_id','include_signature']
        try:
            vals = rec.read(safe_fields)[0]
        except Exception:
            vals = {f: '<unreadable>' for f in safe_fields}
        _logger.info("SNAP_BTN: wizard vals=%s", vals)

        # 1) Mismo dataset que usa Imprimir
        try:
            ds = rec._fetch_dataset()
            _logger.info(
                "SNAP_BTN: dataset listo (tz=%s, dfrom=%s, dto=%s, emps=%s, day_list=%s)",
                ds.get('tz'), ds.get('dfrom'), ds.get('dto'),
                (ds.get('employees').ids if hasattr(ds.get('employees'), 'ids') else ds.get('employees')),
                len(ds.get('day_list') or [])
            )
        except Exception:
            _logger.exception("SNAP_BTN: fallo armando dataset")
            raise

        # 2) Crear snapshot base
        Snap = rec.env['att.report.snapshot']
        emps = ds.get('employees')
        emp_ids = emps if isinstance(emps, list) else getattr(emps, 'ids', [])
        dfrom = ds['dfrom']; dto = ds['dto']
        kind  = rec._context.get('report_kind','general')
        loc   = getattr(rec, 'work_location_id', False)
        name  = "Operativos" if kind == 'general' else "Administrativos"
        name += f" {getattr(dfrom,'date',lambda: dfrom)()}..{getattr(dto,'date',lambda: dto)()}"
        if loc:
            name += f" ({loc.name})"

        _logger.info("SNAP_BTN: creando snapshot name=%s kind=%s emp_ids=%s", name, kind, emp_ids)

        snap = Snap.create({
            'name': name,
            'period_type': 'custom',
            'date_from': dfrom,
            'date_to': dto,
            'report_kind': kind,
            'work_location_id': loc.id if loc else False,
            'employee_ids': [(6, 0, emp_ids)],
            'include_signature': bool(ds.get('include_signature', True)),
        })

        # 3) Congelar con el dataset (aquí se guardan los datos)
        try:
            _logger.info("SNAP_BTN: congelando snapshot id=%s ...", snap.id)
            snap.action_freeze_from_wizard_dataset(ds)
            _logger.info("SNAP_BTN: snapshot %s congelado OK", snap.id)
        except Exception:
            _logger.exception("SNAP_BTN: fallo congelando snapshot id=%s", snap.id)
            raise

        # 4) Abrir el snapshot
        act = {
            'type': 'ir.actions.act_window',
            'res_model': 'att.report.snapshot',
            'view_mode': 'form',
            'res_id': snap.id,
            'target': 'current',
        }
        _logger.info("SNAP_BTN: devolviendo action=%s", act)
        return act