from odoo import api, fields, models, _
from datetime import datetime, timedelta, time
import pytz
from collections import defaultdict
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AdminAttendanceReportWizard(models.TransientModel):
    _name = "admin.attendance.report.wizard"
    _description = "Asistencias - Reporte Administrativos (PDF) - HR Attendance"

    @api.model
    def _default_date_from(self):
        return fields.Datetime.now() - timedelta(days=7)

    @api.model
    def _default_date_to(self):
        return fields.Datetime.now()

    date_from = fields.Datetime(required=True, default=_default_date_from)
    date_to   = fields.Datetime(required=True, default=_default_date_to)

    work_location_id = fields.Many2one(
        "hr.work.location",
        string="Sucursal",
        help="Filtra empleados por su ubicación de trabajo."
    )

    employee_ids = fields.Many2many(
        "hr.employee",
        domain="[('active','=',True), ('is_administrative','=',True)]",
        help="Si se deja vacío, se incluirán todos los administrativos (y por sucursal si se eligió)."
    )

    include_signature = fields.Boolean(default=True)

    def action_print_admin_pdf(self):
        self.ensure_one()
        _logger.info("action_print_admin_pdf llamado para wizard ID: %s", self.id)

        dataset = self.get_dataset()
        _logger.info("Dataset generado, empleados: %s", len(dataset.get('employees', [])))

        return self.env.ref('custom_reports_mooch.action_attendance_admin_pdf').report_action(self, data={'form': dataset})

    def _to_user_tz(self, dt, tz):
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        return dt.astimezone(tz)

    def _make_naive(self, dt, tz):
        """Convierte datetime aware a naive en la zona horaria especificada"""
        if not dt:
            return None
        if dt.tzinfo is not None:
            return dt.astimezone(tz).replace(tzinfo=None)
        return dt

    def _overlap_seconds_same_day(self, start_dt, end_dt, day_date, tz):
        """Segundos del tramo [start_dt, end_dt] que caen dentro del día local 'day_date'."""
        try:
            local_day_start = tz.localize(datetime.combine(day_date, time.min))
            local_day_end   = tz.localize(datetime.combine(day_date, time.max))

            if start_dt.tzinfo is None:
                start_dt = pytz.UTC.localize(start_dt)
            if end_dt and end_dt.tzinfo is None:
                end_dt = pytz.UTC.localize(end_dt)

            end_dt = end_dt or start_dt

            if end_dt < start_dt:
                _logger.warning("End date before start date: %s < %s", end_dt, start_dt)
                return 0

            lo = max(start_dt, local_day_start)
            hi = min(end_dt, local_day_end)

            if hi <= lo:
                return 0

            return int((hi - lo).total_seconds())
        except Exception as e:
            _logger.error("Error en _overlap_seconds_same_day: %s", e)
            return 0

    def _format_hhmm(self, seconds):
        if seconds is None:
            return "00:00"
        total = max(0, int(seconds or 0))
        h = total // 3600
        m = (total % 3600) // 60
        return f"{h:02d}:{m:02d}"

    def _is_rest_day(self, employee, date):
        """Verifica si la fecha es día de descanso para el empleado"""
        weekday = date.weekday()
        rest_days_map = {
            0: employee.rest_monday,
            1: employee.rest_tuesday,
            2: employee.rest_wednesday,
            3: employee.rest_thursday,
            4: employee.rest_friday,
            5: employee.rest_saturday,
            6: employee.rest_sunday,
        }
        return rest_days_map.get(weekday, False)

    def _get_planned_work_hours(self, employee, date):
        """Obtiene horas planificadas del calendario del empleado"""
        cal = (
            employee.resource_calendar_id or
            employee.company_id.resource_calendar_id or
            self.env.company.resource_calendar_id
        )

        if not cal:
            return None, None, None

        dow = str(date.weekday())
        lines = cal.attendance_ids.filtered(
            lambda l: l.dayofweek == dow and (not l.resource_id or l.resource_id == employee.resource_id)
        ).sorted(key=lambda l: l.hour_from)

        if not lines:
            return None, None, None

        # Primer segmento de trabajo
        work_segments = [l for l in lines if not self._is_break_line(l)]
        if not work_segments:
            return None, None, None

        first_segment = work_segments[0]
        expected_start = self._hour_float_to_time(first_segment.hour_from, date)

        # Buscar segmento de comida
        lunch_segment = None
        for i in range(len(lines) - 1):
            if not self._is_break_line(lines[i]) and not self._is_break_line(lines[i + 1]):
                gap = lines[i + 1].hour_from - lines[i].hour_to
                if gap >= 0.5:  # 30 minutos o más
                    lunch_segment = (
                        self._hour_float_to_time(lines[i].hour_to, date),
                        self._hour_float_to_time(lines[i + 1].hour_from, date)
                    )
                    break

        # Último segmento de trabajo
        last_segment = work_segments[-1]
        expected_end = self._hour_float_to_time(last_segment.hour_to, date)

        return expected_start, lunch_segment, expected_end

    def _is_break_line(self, line):
        """Determina si una línea del calendario es descanso/comida"""
        name = (line.name or '').lower()
        return any(keyword in name for keyword in ['descanso', 'comida', 'almuerzo', 'lunch', 'break'])

    def _hour_float_to_time(self, hour_float, date):
        """Convierte 9.5 a datetime(2025-09-22 09:30:00)"""
        hh = int(hour_float)
        mm = int(round((hour_float - hh) * 60))
        return datetime.combine(date, time(hh, mm))

    def get_dataset(self):
        """Construye el dataset consumido por QWeb (consultas en UTC; 'day_list' en LOCAL)."""
        self.ensure_one()
        _logger.info("=== GENERANDO DATASET (v3 day_list local) ===")

        tz = pytz.timezone(self.env.user.tz or 'UTC')

        # 1) Fechas del filtro en UTC
        dfrom_utc = fields.Datetime.from_string(self.date_from)
        dto_utc   = fields.Datetime.from_string(self.date_to)
        if dfrom_utc > dto_utc:
            dfrom_utc, dto_utc = dto_utc, dfrom_utc

        # 2) Equivalentes en LOCAL (solo display y para construir 'day_list')
        dfrom_local = self._to_user_tz(dfrom_utc, tz)
        dto_local   = self._to_user_tz(dto_utc, tz)

        # 3) day_list basada en LOCAL (evita que se “salte” al día siguiente por TZ)
        day_list_dates = []
        cur = dfrom_local.date()
        end = dto_local.date()
        while cur <= end:
            day_list_dates.append(cur)
            cur += timedelta(days=1)

        # 3.1 Etiquetas “lun/06/oct” preformateadas para el XML
        spanish_days   = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']
        spanish_months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
        date_labels = {}
        for d in day_list_dates:
            label = f"{spanish_days[d.weekday()]}/{d.day:02d}/{spanish_months[d.month-1]}"
            date_labels[d.strftime('%Y-%m-%d')] = label

        # 4) Empleados
        domain = [('active', '=', True), ('is_administrative', '=', True)]
        if self.work_location_id:
            domain.append(('work_location_id', '=', self.work_location_id.id))
        employees = self.employee_ids or self.env['hr.employee'].search(domain, order='work_location_id,name')

        # 5) AUSENCIAS (UTC para buscar; convertir a LOCAL para cruzar con day_list)
        Leave = self.env['hr.leave']
        leaves = Leave.search([
            ('employee_id', 'in', employees.ids),
            ('state', '=', 'validate'),
            ('date_from', '<=', dto_utc),
            ('date_to',   '>=', dfrom_utc),
        ])
        leave_index = defaultdict(dict)
        for leave in leaves:
            lfrom_loc = self._to_user_tz(leave.date_from, tz).date() if leave.date_from else None
            lto_loc   = self._to_user_tz(leave.date_to,   tz).date() if leave.date_to   else None
            if not lfrom_loc or not lto_loc:
                continue
            start_date = max(lfrom_loc, dfrom_local.date())
            end_date   = min(lto_loc,   dto_local.date())
            cd = start_date
            while cd <= end_date:
                leave_index[leave.employee_id.id][cd] = {'status': leave.holiday_status_id.name, 'type': 'leave'}
                cd += timedelta(days=1)

        # 6) ASISTENCIAS (UTC)
        Attend = self.env['hr.attendance']
        atts = Attend.search([
            ('employee_id', 'in', employees.ids),
            '|',
            '&', ('check_in', '>=', dfrom_utc), ('check_in', '<=', dto_utc),
            '&', ('check_in', '<',  dfrom_utc), ('check_out', '>=', dfrom_utc),
        ], order='employee_id, check_in')

        # Filtrar inconsistencias
        atts = self.env['hr.attendance'].browse([
            a.id for a in atts if (not a.check_out) or (a.check_out >= a.check_in)
        ])

        # 7) Resumen por empleado / día LOCAL
        per_emp_day_summary = defaultdict(dict)
        for emp in employees:
            emp_atts = atts.filtered(lambda a: a.employee_id.id == emp.id)

            # Agrupar por día LOCAL completo (pares in/out)
            day_asist = defaultdict(list)  # { date(): [(cin_loc, cout_loc), ...] }
            for att in emp_atts:
                cin_loc  = self._to_user_tz(att.check_in, tz)
                cout_loc = self._to_user_tz(att.check_out, tz) if att.check_out else None
                if cout_loc:
                    day_asist[cin_loc.date()].append((cin_loc, cout_loc))

            for day in day_list_dates:
                asist = list(day_asist.get(day, []))
                asist.sort(key=lambda x: x[0])

                lunch_out = lunch_in = None
                first_in = last_out = None

                if len(asist) >= 2:
                    first_blk, second_blk = asist[0], asist[1]
                    lunch_out = first_blk[1]
                    lunch_in  = second_blk[0]
                    if not (timedelta(minutes=30) <= (lunch_in - lunch_out) <= timedelta(hours=2)):
                        lunch_out = lunch_in = None

                if asist:
                    first_in = asist[0][0]
                    last_out = asist[-1][1]
                elif len(asist) == 1:
                    first_in = asist[0][0]
                    last_out = asist[0][1]

                work_secs = 0
                if first_in and last_out and last_out > first_in:
                    for cin, cout in asist:
                        work_secs += int((cout - cin).total_seconds())
                    if lunch_out and lunch_in:
                        work_secs -= int((lunch_in - lunch_out).total_seconds())

                status = "Asistencia"
                retardo_seconds = 0
                if self._is_rest_day(emp, day):
                    status = "Descanso"; work_secs = 0
                elif day in leave_index.get(emp.id, {}):
                    lt = (leave_index[emp.id][day]['status'] or '').lower()
                    if 'vacacion' in lt or 'vacación' in lt:
                        status = "Vacaciones"
                    elif 'permiso' in lt:
                        status = "Permiso c/goce" if 'goce' in lt else "Permiso s/goce"
                    else:
                        status = leave_index[emp.id][day]['status']
                    work_secs = 0
                elif not first_in and not last_out:
                    status = "Falta"
                elif first_in:
                    expected_start, lunch_segment, expected_end = self._get_planned_work_hours(emp, day)
                    if expected_start:
                        first_in_naive = self._make_naive(first_in, tz)
                        if first_in_naive > expected_start:
                            retardo_seconds = int((first_in_naive - expected_start).total_seconds())
                            if retardo_seconds >= 60:
                                status = "Retardo"

                fmt = lambda dt: dt.strftime('%H:%M') if dt else '—'
                key = day.strftime('%Y-%m-%d')
                per_emp_day_summary[str(emp.id)][key] = {
                    'first_in_s': fmt(first_in),
                    'lunch_out_s': fmt(lunch_out),
                    'lunch_in_s': fmt(lunch_in),
                    'last_out_s': fmt(last_out),
                    'work_str': self._format_hhmm(work_secs),
                    'lunch_str': self._format_hhmm(int((lunch_in - lunch_out).total_seconds()) if lunch_out and lunch_in else 0),
                    'retardo': self._format_hhmm(retardo_seconds),
                    'status': status,
                }

        # 8) Serialización empleados
        employees_data = [{
            'id': emp.id,
            'name': emp.name,
            'barcode': emp.barcode or 'No asignado',
            'department_name': emp.department_id.name if emp.department_id else '—',
            'work_location_name': emp.work_location_id.name if emp.work_location_id else '—',
        } for emp in employees]

        # 9) Totales de retardo
        per_emp_total_retardo = {}
        for emp in employees:
            total_min = 0
            for d in day_list_dates:
                ds = d.strftime('%Y-%m-%d')
                r = per_emp_day_summary.get(str(emp.id), {}).get(ds, {}).get('retardo', '00:00')
                if r not in ('00:00', '—'):
                    try:
                        h, m = map(int, r.split(':')); total_min += h*60 + m
                    except Exception:
                        pass
            per_emp_total_retardo[str(emp.id)] = f"{total_min//60:02d}:{total_min%60:02d}"

        _logger.info("Dataset OK (local days) - Empleados:%s Días:%s",
                    len(employees_data), len(day_list_dates))

        return {
            'title': "Reporte Administrativos (Asistencias) - HR",
            'employees': employees_data,
            'day_list': [d.strftime('%Y-%m-%d') for d in day_list_dates],
            'date_labels': date_labels,  # << nuevo
            'per_emp_day_summary': dict(per_emp_day_summary),
            'per_emp_total_retardo': per_emp_total_retardo,
            'dfrom': dfrom_local.strftime('%Y-%m-%d %H:%M'),
            'dto':   dto_local.strftime('%Y-%m-%d %H:%M'),
            'tz': self.env.user.tz or 'UTC',
            'include_signature': self.include_signature,
            'cards_per_page': 2,
            'date_labels': date_labels,
        }


    def action_save_snapshot(self):
        self.ensure_one()
        if not self.date_from or not self.date_to:
            raise UserError(_("Debes indicar fecha inicial y final."))

        # 1) Construir dataset con TU lógica actual
        dataset = self.get_dataset()  # <- ya devuelve dict JSON-serializable para QWeb

        Snap = self.env['att.report.snapshot']

        # 2) Nombre amigable + parámetros base
        dfrom_str = fields.Date.to_date(self.date_from).strftime('%Y-%m-%d')
        dto_str   = fields.Date.to_date(self.date_to).strftime('%Y-%m-%d')
        wl_name   = self.work_location_id.name if self.work_location_id else False
        name = f"Administrativos {dfrom_str}..{dto_str}" + (f" ({wl_name})" if wl_name else "")

        base_vals = {
            'name': name,
            'period_type': 'custom',
            'report_kind': 'admin',
            'date_from': self.date_from,
            'date_to': self.date_to,
            'work_location_id': self.work_location_id.id or False,
            'employee_ids': [(6, 0, self.employee_ids.ids)] if self.employee_ids else False,
            'include_signature': bool(getattr(self, 'include_signature', True)),
        }

        # 3) Reutilizar snapshot si ya existe (evita violar la unique)
        snap = Snap.search([
            ('period_type', '=', 'custom'),
            ('report_kind', '=', 'admin'),
            ('date_from', '=', self.date_from),
            ('date_to',   '=', self.date_to),
            ('work_location_id', '=', self.work_location_id.id or False),
        ], limit=1)

        if snap:
            snap.write(base_vals)  # actualiza nombre/empleados por si cambian
        else:
            snap = Snap.create(base_vals)

        # 4) Congelar con el dataset del wizard (sin recalcular)
        snap.action_freeze_from_wizard_dataset(dataset)

        # 5) Abrir el documento en Documentos si existe; si no, abrir el snapshot
        if snap.document_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'documents.document',
                'view_mode': 'form',
                'res_id': snap.document_id.id,
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'att.report.snapshot',
            'view_mode': 'form',
            'res_id': snap.id,
        }