# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, date, timedelta
from collections import defaultdict
import pytz
import logging

_logger = logging.getLogger(__name__)

class AdminAttendanceReportPDF(models.AbstractModel):
    _name = 'report.custom_reports_mooch.attendance_admin_pdf_document'
    _description = 'Reporte Administrativos PDF'

    def _get_user_timezone(self):
        """Obtiene la zona horaria del usuario"""
        return pytz.timezone(self.env.user.tz or 'UTC')

    def _to_user_timezone(self, dt_utc):
        """Convierte datetime UTC a la zona horaria del usuario"""
        if not dt_utc:
            return None
        user_tz = self._get_user_timezone()
        if dt_utc.tzinfo is None:
            dt_utc = pytz.utc.localize(dt_utc)
        return dt_utc.astimezone(user_tz)

    def _get_attendance_data(self, employee_ids, date_from, date_to):
        """
        Obtiene datos de asistencia desde hr.attendance para los empleados y rango de fechas especificados
        """
        Attendance = self.env['hr.attendance']
        
        # Convertir a datetime para la consulta
        dt_from = datetime.combine(date_from, datetime.min.time())
        dt_to = datetime.combine(date_to, datetime.max.time())
        
        # Buscar asistencias que se superpongan con el rango
        domain = [
            ('employee_id', 'in', employee_ids),
            ('check_in', '<=', dt_to),
            '|', ('check_out', '=', False), ('check_out', '>=', dt_from)
        ]
        
        attendances = Attendance.search(domain, order='employee_id, check_in')
        return attendances

    def _process_employee_attendance(self, attendances, date_from, date_to):
        """
        Procesa las asistencias por empleado y día
        """
        result = defaultdict(lambda: defaultdict(list))
        
        for att in attendances:
            emp_id = att.employee_id.id
            check_in_tz = self._to_user_timezone(att.check_in) if att.check_in else None
            check_out_tz = self._to_user_timezone(att.check_out) if att.check_out else None
            
            if check_in_tz:
                check_in_date = check_in_tz.date()
                if date_from <= check_in_date <= date_to:
                    result[emp_id][check_in_date].append(('in', check_in_tz))
            
            if check_out_tz:
                check_out_date = check_out_tz.date()
                if date_from <= check_out_date <= date_to:
                    result[emp_id][check_out_date].append(('out', check_out_tz))
        
        return result

    def _calculate_daily_summary(self, events):
        """
        Calcula resumen diario a partir de eventos de entrada/salida
        """
        if not events:
            return {
                'first_in': None,
                'last_out': None,
                'work_seconds': 0,
                'work_str': '00:00'
            }
        
        # Ordenar eventos por tiempo
        sorted_events = sorted(events, key=lambda x: x[1])
        
        first_in = None
        last_out = None
        work_seconds = 0
        
        # Encontrar primera entrada y última salida
        for event_type, event_time in sorted_events:
            if event_type == 'in' and (first_in is None or event_time < first_in):
                first_in = event_time
            if event_type == 'out' and (last_out is None or event_time > last_out):
                last_out = event_time
        
        # Calcular tiempo trabajado
        if first_in and last_out and last_out > first_in:
            work_seconds = int((last_out - first_in).total_seconds())
        
        # Formatear a HH:MM
        hours = work_seconds // 3600
        minutes = (work_seconds % 3600) // 60
        work_str = f"{hours:02d}:{minutes:02d}"
        
        return {
            'first_in': first_in,
            'last_out': last_out,
            'work_seconds': work_seconds,
            'work_str': work_str
        }

    def _get_leave_data(self, employee_ids, date_from, date_to):
        """
        Obtiene datos de ausencias (vacaciones, permisos)
        """
        Leave = self.env['hr.leave']
        
        leaves = Leave.search([
            ('employee_id', 'in', employee_ids),
            ('state', '=', 'validate'),
            ('request_date_from', '<=', date_to),
            ('request_date_to', '>=', date_from)
        ])
        
        leave_index = defaultdict(dict)
        for leave in leaves:
            for emp_id in employee_ids:
                if leave.employee_id.id == emp_id:
                    start_date = max(leave.request_date_from, date_from)
                    end_date = min(leave.request_date_to, date_to)
                    
                    current_date = start_date
                    while current_date <= end_date:
                        leave_index[emp_id][current_date] = leave.holiday_status_id.name or 'Ausencia'
                        current_date += timedelta(days=1)
        
        return leave_index

    def _generate_report_data(self, wizard, date_from, date_to):
        """
        Genera todos los datos necesarios para el reporte
        """
        # Obtener empleados
        if wizard.employee_ids:
            employees = wizard.employee_ids
        else:
            employees = self.env['hr.employee'].search([
                ('active', '=', True),
                ('is_administrative', '=', True)
            ])
        
        employee_ids = employees.ids
        
        # Obtener datos de asistencia
        attendances = self._get_attendance_data(employee_ids, date_from, date_to)
        attendance_data = self._process_employee_attendance(attendances, date_from, date_to)
        
        # Obtener datos de ausencias
        leave_data = self._get_leave_data(employee_ids, date_from, date_to)
        
        # Generar lista de días
        day_list = []
        current_date = date_from
        while current_date <= date_to:
            day_list.append(current_date)
            current_date += timedelta(days=1)
        
        # Preparar datos finales
        result = {
            'employees': employees,
            'day_list': day_list,
            'per_emp_day_summary': {},
            'dfrom': date_from,
            'dto': date_to,
            'tz': self._get_user_timezone().zone,
            'include_signature': wizard.include_signature,
            'title': 'Reporte Administrativos'
        }
        
        # Calcular resumen por empleado y día
        for emp in employees:
            emp_id = emp.id
            result['per_emp_day_summary'][emp_id] = {}
            
            for day in day_list:
                day_events = attendance_data.get(emp_id, {}).get(day, [])
                daily_summary = self._calculate_daily_summary(day_events)
                
                # Verificar si es día de descanso
                is_rest_day = self._is_rest_day(emp, day)
                
                # Verificar si hay ausencia
                leave_status = leave_data.get(emp_id, {}).get(day)
                
                result['per_emp_day_summary'][emp_id][day] = {
                    'first_in_s': daily_summary['first_in'].strftime('%H:%M') if daily_summary['first_in'] else '—',
                    'last_out_s': daily_summary['last_out'].strftime('%H:%M') if daily_summary['last_out'] else '—',
                    'work_str': daily_summary['work_str'],
                    'lunch_out_s': '—',
                    'lunch_in_s': '—',
                    'lunch_str': '00:00',
                    'is_rest_day': is_rest_day,
                    'leave_status': leave_status
                }
        
        return result

    def _is_rest_day(self, emp, day):
        """
        Verifica si el día es de descanso para el empleado
        """
        dow = day.weekday()
        rest_days = {
            0: emp.rest_monday,
            1: emp.rest_tuesday,
            2: emp.rest_wednesday,
            3: emp.rest_thursday,
            4: emp.rest_friday,
            5: emp.rest_saturday,
            6: emp.rest_sunday
        }
        return rest_days.get(dow, False)

    def _get_report_values(self, docids, data=None):
        _logger.info("=== _get_report_values llamado ===")
        _logger.info("docids: %s", docids)
        _logger.info("data recibida: %s", data)
        
        # Si docids está vacío pero tenemos active_id en el contexto, usarlo
        if not docids and data and data.get('context', {}).get('active_id'):
            docids = [data['context']['active_id']]
            _logger.info("Usando active_id del contexto: %s", docids)
        
        # Obtener datos
        if data and 'form' in data:
            dataset = data['form']
            _logger.info("Usando datos de data['form']")
        else:
            wizard = self.env['admin.attendance.report.wizard'].browse(docids)
            if wizard.exists():
                dataset = wizard.get_dataset()
                _logger.info("Generando datos desde wizard")
            else:
                _logger.error("Wizard no existe")
                dataset = {}
        
        _logger.info("Datos enviados al template:")
        _logger.info(" - Empleados: %s", len(dataset.get('employees', [])))
        _logger.info(" - Días: %s", len(dataset.get('day_list', [])))
        
        return {
            'doc_ids': docids,
            'doc_model': 'admin.attendance.report.wizard',
            'docs': self.env['admin.attendance.report.wizard'].browse(docids),
            'data': {'form': dataset},
        }