# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import datetime, timedelta, time
import pytz
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)

class AdminAttendanceReportWizard(models.TransientModel):
    _name = "admin.attendance.report.wizard"
    _description = "Asistencias - Reporte Administrativos (PDF)"

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

    # ---------------- Disparador del PDF ----------------
    def action_print_admin_pdf(self):
        self.ensure_one()
        _logger.info("action_print_admin_pdf llamado para wizard ID: %s", self.id)
        
        # Generar dataset
        dataset = self.get_dataset()
        _logger.info("Dataset generado, empleados: %s", len(dataset.get('employees', [])))
        
        # DEBUG: Verificar qué datos se están enviando
        _logger.info("Datos enviados al reporte:")
        _logger.info(" - Fecha desde: %s", dataset.get('dfrom'))
        _logger.info(" - Fecha hasta: %s", dataset.get('dto'))
        _logger.info(" - Empleados: %s", len(dataset.get('employees', [])))
        _logger.info(" - Días: %s", len(dataset.get('day_list', [])))
        
        return self.env.ref('custom_reports_mooch.action_attendance_admin_pdf').report_action(self, data={'form': dataset})
    # ---------------- Helpers ----------------
    def _to_user_tz(self, dt, tz):
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        return dt.astimezone(tz)

    def _overlap_seconds_same_day(self, start_dt, end_dt, day_date, tz):
        """Segundos del tramo [start_dt, end_dt] que caen dentro del día local 'day_date'."""
        try:
            local_day_start = tz.localize(datetime.combine(day_date, time.min))
            local_day_end   = tz.localize(datetime.combine(day_date, time.max))
            
            # Asegurar que las fechas estén en la misma zona horaria
            if start_dt.tzinfo is None:
                start_dt = pytz.UTC.localize(start_dt)
            if end_dt and end_dt.tzinfo is None:
                end_dt = pytz.UTC.localize(end_dt)
            
            end_dt = end_dt or start_dt  # Si no hay check_out, usar check_in
            
            # Validar que end_dt no sea anterior a start_dt
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
        """
        Convierte segundos a formato HH:MM
        """
        if seconds is None:
            return "00:00"
        total = max(0, int(seconds or 0))
        h = total // 3600
        m = (total % 3600) // 60
        return f"{h:02d}:{m:02d}"

# ---------------- Dataset del reporte ----------------
    def get_dataset(self):
        """
        Construye el dataset consumido por QWeb
        """
        self.ensure_one()
        _logger.info("=== GENERANDO DATASET CON LÓGICA DE STATUS ===")
        _logger.info("Fecha from: %s, Fecha to: %s", self.date_from, self.date_to)
        tz = pytz.timezone(self.env.user.tz or 'UTC')

        dfrom = fields.Datetime.from_string(self.date_from)
        dto   = fields.Datetime.from_string(self.date_to)
        if dfrom > dto:
            dfrom, dto = dto, dfrom

        # Rango en zona del usuario
        dfrom_local = self._to_user_tz(dfrom, tz)
        dto_local   = self._to_user_tz(dto, tz)

        day_list = []
        cur = dfrom_local.date()
        end = dto_local.date()
        while cur <= end:
            day_list.append(cur)
            cur += timedelta(days=1)

        # Empleados administrativos
        domain = [('active', '=', True), ('is_administrative', '=', True)]
        if self.work_location_id:
            domain.append(('work_location_id', '=', self.work_location_id.id))
        employees = self.employee_ids or self.env['hr.employee'].search(domain, order='work_location_id,name')

        # ===== NUEVO: Obtener ausencias (vacaciones, permisos) =====
        # Buscar leaves (ausencias) en el rango de fechas
        Leave = self.env['hr.leave']
        leave_domain = [
            ('employee_id', 'in', employees.ids),
            ('state', '=', 'validate'),  # Solo ausencias aprobadas
            ('date_from', '<=', dto_local.date()),
            ('date_to', '>=', dfrom_local.date()),
        ]
        leaves = Leave.search(leave_domain)
        
        # Crear índice de ausencias por empleado y día
        leave_index = defaultdict(dict)
        for leave in leaves:
            start_date = max(leave.date_from.date(), dfrom_local.date())
            end_date = min(leave.date_to.date(), dto_local.date())
            
            current_date = start_date
            while current_date <= end_date:
                leave_index[leave.employee_id.id][current_date] = {
                    'status': leave.holiday_status_id.name,
                    'type': 'leave'
                }
                current_date += timedelta(days=1)
        # ===== FIN NUEVO =====

        # Asistencias que toquen el rango
        Attend = self.env['hr.attendance']
        att_domain = [
            ('employee_id', 'in', employees.ids or [-1]),
            '|',
            '&',  # Asistencias que empezaron Y terminaron en el rango
                ('check_in', '>=', dfrom),
                ('check_in', '<=', dto),
            '&',  # O asistencias que empezaron antes pero terminaron en el rango
                ('check_in', '<', dfrom),
                ('check_out', '>=', dfrom),
        ]
        atts = Attend.search(att_domain, order='employee_id, check_in')

        # DEBUG: Verificar cuántas asistencias se encontraron
        _logger.info("Asistencias encontradas: %s", len(atts))
        for att in atts:
            _logger.info(" - Empleado: %s, Check-in: %s, Check-out: %s", 
                        att.employee_id.name, att.check_in, att.check_out)

# ===== VALIDAR Y FILTRAR ASISTENCIAS CON DATOS INCORRECTOS =====
        valid_atts = []
        for att in atts:
            if att.check_out and att.check_out < att.check_in:
                _logger.warning("Asistencia con check_out anterior a check_in: %s", att.id)
                continue
            
            if att.check_out and (att.check_out - att.check_in) > timedelta(days=1):
                _logger.warning("Asistencia con duración mayor a 1 día: %s (%.1f días)", 
                            att.id, (att.check_out - att.check_in).total_seconds() / 86400)
            
            valid_atts.append(att)

        # CONVERTIR la lista de vuelta a un Recordset de Odoo
        att_ids = [att.id for att in valid_atts]
        atts = self.env['hr.attendance'].browse(att_ids)
        _logger.info("Asistencias válidas después de filtrar: %s", len(atts))
# ===== FIN VALIDACIÓN =====

        LUNCH_MIN = timedelta(minutes=30)
        LUNCH_MAX = timedelta(hours=2)

        per_emp_day_summary = defaultdict(dict)

        for emp in employees:
            emp_id = emp.id
            emp_atts = atts.filtered(lambda a, emp=emp: a.employee_id.id == emp.id and (a.check_out or a.check_in) >= dfrom and a.check_in <= dto)

            # Convertir a TZ local
            intervals = []
            for a in emp_atts:
                cin = self._to_user_tz(a.check_in, tz)
                cout = self._to_user_tz(a.check_out, tz) if a.check_out else None
                intervals.append((cin, cout))

            for day in day_list:
                ins  = []
                outs = []
                work_secs = 0

                for cin, cout in intervals:
                    work_secs += self._overlap_seconds_same_day(cin, cout or cin, day, tz)
                    if cin.date() == day:
                        ins.append(cin)
                    if cout and cout.date() == day:
                        outs.append(cout)

                first_in = ins and min(ins) or None
                last_out = outs and max(outs) or None

                # Detectar tiempo de comida
                local_points = []
                local_day_start = tz.localize(datetime.combine(day, time.min))
                local_day_end   = tz.localize(datetime.combine(day, time.max))
                for cin, cout in intervals:
                    s = max(cin, local_day_start)
                    e = min(cout or cin, local_day_end)
                    if e > s:
                        local_points.append((s, e))
                local_points.sort(key=lambda x: x[0])

                lunch_out = None
                lunch_in = None
                max_gap = timedelta(0)
                for (s1, e1), (s2, e2) in zip(local_points, local_points[1:]):
                    gap = s2 - e1
                    if LUNCH_MIN <= gap <= LUNCH_MAX and gap > max_gap:
                        max_gap = gap
                        lunch_out = e1
                        lunch_in = s2

                lunch_secs = int(max_gap.total_seconds()) if lunch_out and lunch_in else 0
                fmt = lambda dt: dt and dt.strftime('%H:%M') or '—'

                # ===== LÓGICA MEJORADA DE STATUS =====
                status = "Asistencia"
                retardo_seconds = 0
                
                # 1. Verificar si es día de descanso
                is_rest_day = self._is_rest_day(emp, day)
                if is_rest_day:
                    status = "Descanso"
                    work_secs = 0  # No contar horas en día de descanso
                
                # 2. Verificar si hay ausencia (vacaciones/permisos)
                elif day in leave_index.get(emp_id, {}):
                    leave_info = leave_index[emp_id][day]
                    leave_type = leave_info['status']
                    
                    if 'vacacion' in leave_type.lower() or 'vacación' in leave_type.lower():
                        status = "Vacaciones"
                    elif 'permiso' in leave_type.lower():
                        if 'goce' in leave_type.lower():
                            status = "Permiso c/goce"
                        else:
                            status = "Permiso s/goce"
                    else:
                        status = leave_type
                    work_secs = 0  # No contar horas en ausencia
                
                # 3. Verificar asistencia normal
                elif work_secs == 0:
                    status = "Falta"
                
                # 4. Verificar retardo (menos de 8 horas)
                elif work_secs < 28800:  # 8 horas = 28800 segundos
                    status = "Retardo"
                    expected_seconds = 28800
                    retardo_seconds = expected_seconds - work_secs
                
                # 5. Asistencia completa
                else:
                    status = "Asistencia"
                # ===== FIN LÓGICA DE STATUS =====

                day_str = day.strftime('%Y-%m-%d')
                per_emp_day_summary[emp_id][day_str] = {
                    'first_in_s': fmt(first_in),
                    'lunch_out_s': fmt(lunch_out),
                    'lunch_in_s': fmt(lunch_in),
                    'last_out_s': fmt(last_out),
                    'work_str': self._format_hhmm(work_secs),
                    'lunch_str': self._format_hhmm(lunch_secs),
                    'retardo': self._format_hhmm(retardo_seconds),
                    'status': status
                }

        # Serializar empleados
        employees_data = []
        for emp in employees:
            employees_data.append({
                'id': emp.id,
                'name': emp.name,
                'barcode': emp.barcode or 'No asignado',
                'department_name': emp.department_id.name if emp.department_id else '—',
                'work_location_name': emp.work_location_id.name if emp.work_location_id else '—',
            })

        _logger.info("Dataset generado exitosamente")
        _logger.info("Empleados: %s, Días: %s", len(employees_data), len(day_list))

        return {
            'title': "Reporte Administrativos (Asistencias)",
            'employees': employees_data,
            'day_list': [day.strftime('%Y-%m-%d') for day in day_list],
            'per_emp_day_summary': dict(per_emp_day_summary),
            'dfrom': dfrom_local.strftime('%Y-%m-%d %H:%M'),
            'dto': dto_local.strftime('%Y-%m-%d %H:%M'),
            'tz': self.env.user.tz or 'UTC',
            'include_signature': self.include_signature,
            'cards_per_page': 2,
        }

    # ===== NUEVO MÉTODO: Verificar día de descanso =====
    def _is_rest_day(self, employee, date):
        """
        Verifica si la fecha es día de descanso para el empleado
        basado en su calendario de trabajo
        """
        # Obtener día de la semana (0=lunes, 6=domingo)
        weekday = date.weekday()
        
        # Mapear días de descanso del empleado
        rest_days_map = {
            0: employee.rest_monday,    # Lunes
            1: employee.rest_tuesday,   # Martes
            2: employee.rest_wednesday, # Miércoles
            3: employee.rest_thursday,  # Jueves
            4: employee.rest_friday,    # Viernes
            5: employee.rest_saturday,  # Sábado
            6: employee.rest_sunday,    # Domingo
        }
        
        return rest_days_map.get(weekday, False)