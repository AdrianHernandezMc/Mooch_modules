# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import datetime, timedelta, time
import pytz
from collections import defaultdict
import logging

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
        """Construye el dataset consumido por QWeb - DETECCIÓN CORRECTA DE COMIDA"""
        self.ensure_one()
        _logger.info("=== GENERANDO DATASET CON DETECCIÓN CORRECTA DE COMIDA ===")
        
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

        # ===== AUSENCIAS (VACACIONES/PERMISOS) =====
        Leave = self.env['hr.leave']
        leave_domain = [
            ('employee_id', 'in', employees.ids),
            ('state', '=', 'validate'),
            ('date_from', '<=', dto_local.date()),
            ('date_to', '>=', dfrom_local.date()),
        ]
        leaves = Leave.search(leave_domain)
        
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

        # ===== ASISTENCIAS HR.ATTENDANCE =====
        Attend = self.env['hr.attendance']
        att_domain = [
            ('employee_id', 'in', employees.ids),
            '|',
            '&', ('check_in', '>=', dfrom), ('check_in', '<=', dto),
            '&', ('check_in', '<', dfrom), ('check_out', '>=', dfrom),
        ]
        atts = Attend.search(att_domain, order='employee_id, check_in')

        # Filtrar asistencias válidas
        valid_atts = []
        for att in atts:
            if att.check_out and att.check_out < att.check_in:
                _logger.warning("Asistencia con check_out anterior a check_in: %s", att.id)
                continue
            valid_atts.append(att)

        att_ids = [att.id for att in valid_atts]
        atts = self.env['hr.attendance'].browse(att_ids)

        # ===== PROCESAMIENTO MEJORADO - DETECCIÓN CORRECTA DE COMIDA =====
        per_emp_day_summary = defaultdict(dict)

        for emp in employees:
            emp_id = emp.id
            emp_atts = atts.filtered(lambda a: a.employee_id.id == emp.id)

            # Agrupar asistencias COMPLETAS por día (check_in + check_out)
            day_asistencias = defaultdict(list)
            for att in emp_atts:
                cin = self._to_user_tz(att.check_in, tz)
                cout = self._to_user_tz(att.check_out, tz) if att.check_out else None
                
                # Solo considerar asistencias completas (con check_out)
                if cout:
                    day_asistencias[cin.date()].append((cin, cout))  # (entrada, salida)

            for day in day_list:
                asistencias = day_asistencias.get(day, [])
                asistencias.sort(key=lambda x: x[0])  # Ordenar por hora de entrada

                # ===== DETECCIÓN CORRECTA DE COMIDA =====
                lunch_out = None
                lunch_in = None
                first_in = None
                last_out = None
                
                if len(asistencias) >= 2:
                    # Para detectar comida: necesitamos al menos 2 asistencias
                    # La comida está entre el check_out de la primera y el check_in de la segunda
                    primera_asistencia = asistencias[0]
                    segunda_asistencia = asistencias[1]
                    
                    # Salida a comer = check_out de la primera asistencia
                    lunch_out = primera_asistencia[1]  # 10:25
                    # Regreso de comer = check_in de la segunda asistencia  
                    lunch_in = segunda_asistencia[0]   # 10:26
                    
                    # Verificar que sea un tiempo razonable para comida (30min - 2hrs)
                    tiempo_comida = lunch_in - lunch_out
                    if not (timedelta(minutes=30) <= tiempo_comida <= timedelta(hours=2)):
                        # Si no es un tiempo razonable, no es comida
                        lunch_out = None
                        lunch_in = None
                
                # Primera entrada y última salida del día
                if asistencias:
                    first_in = asistencias[0][0]  # Primera entrada del día
                    last_out = asistencias[-1][1]  # Última salida del día
                
                # Si solo hay una asistencia, usar esa para entrada/salida
                elif len(asistencias) == 1:
                    first_in = asistencias[0][0]
                    last_out = asistencias[0][1]

                # Log para debugging
                _logger.debug("Día %s - Asistencias: %s", day, [
                    (cin.strftime('%H:%M'), cout.strftime('%H:%M')) for cin, cout in asistencias
                ])
                _logger.debug("Comida detectada: %s a %s", 
                            lunch_out.strftime('%H:%M') if lunch_out else "None", 
                            lunch_in.strftime('%H:%M') if lunch_in else "None")

                # Calcular horas trabajadas (considerando comida)
                work_secs = 0
                if first_in and last_out and last_out > first_in:
                    # Sumar tiempo de todas las asistencias
                    for cin, cout in asistencias:
                        work_secs += int((cout - cin).total_seconds())
                    
                    # Restar tiempo de comida si se detectó
                    if lunch_out and lunch_in:
                        work_secs -= int((lunch_in - lunch_out).total_seconds())

                # ===== LÓGICA DE STATUS (MANTENER EXACTA) =====
                status = "Asistencia"
                retardo_seconds = 0
                
                # 1. Verificar día de descanso
                is_rest_day = self._is_rest_day(emp, day)
                if is_rest_day:
                    status = "Descanso"
                    work_secs = 0
                
                # 2. Verificar ausencias
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
                    work_secs = 0
                
                # 3. Verificar si hay asistencia
                elif not first_in and not last_out:
                    status = "Falta"
                
                # 4. Verificar retardo
                elif first_in:
                    expected_start, lunch_segment, expected_end = self._get_planned_work_hours(emp, day)
                    
                    if expected_start:
                        first_in_naive = self._make_naive(first_in, tz)
                        expected_start_naive = expected_start
                        
                        if first_in_naive and expected_start_naive and first_in_naive > expected_start_naive:
                            retardo_seconds = int((first_in_naive - expected_start_naive).total_seconds())
                            if retardo_seconds > 300:  # 5 minutos de tolerancia
                                status = "Retardo"
                
                # 5. Asistencia normal
                else:
                    status = "Asistencia"

                # Formatear resultados
                fmt = lambda dt: dt and dt.strftime('%H:%M') or '—'
                day_str = day.strftime('%Y-%m-%d')
                
                per_emp_day_summary[emp_id][day_str] = {
                    'first_in_s': fmt(first_in),
                    'lunch_out_s': fmt(lunch_out),  # Salida a comer (check_out primera)
                    'lunch_in_s': fmt(lunch_in),    # Regreso de comer (check_in segunda)
                    'last_out_s': fmt(last_out),    # Salida final (check_out última)
                    'work_str': self._format_hhmm(work_secs),
                    'lunch_str': self._format_hhmm(int((lunch_in - lunch_out).total_seconds()) if lunch_out and lunch_in else 0),
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

        # ===== CALCULAR TOTAL DE RETARDOS POR EMPLEADO =====
        per_emp_total_retardo = {}

        for emp in employees:
            emp_id = emp.id
            total_retardo_minutos = 0
            
            for day in day_list:
                day_str = day.strftime('%Y-%m-%d')
                day_data = per_emp_day_summary.get(emp_id, {}).get(day_str, {})
                retardo_str = day_data.get('retardo', '00:00')
                
                # Convertir "HH:MM" a minutos
                if retardo_str and retardo_str != '00:00' and retardo_str != '—':
                    try:
                        hours, minutes = map(int, retardo_str.split(':'))
                        total_retardo_minutos += hours * 60 + minutes
                    except (ValueError, AttributeError):
                        # Si hay error en la conversión, ignorar
                        pass
            
            # Convertir minutos totales a formato "HH:MM"
            total_hours = total_retardo_minutos // 60
            total_minutes = total_retardo_minutos % 60
            per_emp_total_retardo[str(emp_id)] = f"{total_hours:02d}:{total_minutes:02d}"

        _logger.info("Total de retardos calculados para %s empleados", len(per_emp_total_retardo))

        _logger.info("Dataset con detección correcta de comida generado exitosamente")
        _logger.info("Empleados: %s, Días: %s", len(employees_data), len(day_list))


        return {
            'title': "Reporte Administrativos (Asistencias) - HR",
            'employees': employees_data,
            'day_list': [day.strftime('%Y-%m-%d') for day in day_list],
            'per_emp_day_summary': dict(per_emp_day_summary),
            'per_emp_total_retardo': per_emp_total_retardo,
            'dfrom': dfrom_local.strftime('%Y-%m-%d %H:%M'),
            'dto': dto_local.strftime('%Y-%m-%d %H:%M'),
            'tz': self.env.user.tz or 'UTC',
            'include_signature': self.include_signature,
            'cards_per_page': 2,
        }