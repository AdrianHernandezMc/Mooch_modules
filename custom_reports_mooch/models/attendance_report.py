# -*- coding: utf-8 -*-
from odoo import models
from datetime import timedelta, datetime

# ======= Constantes de formato =======
SPANISH_WEEKDAYS = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
SPANISH_MONTHS = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

def _fmt_hhmm_from_seconds(seconds):
    if seconds is None or seconds == 0:
        return '00:00'
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)  # Convertir a integer
    m = int((seconds % 3600) // 60)  # Convertir a integer
    return f"{h:02d}:{m:02d}"

def _title_spanish(dt):
    wd = SPANISH_WEEKDAYS[dt.weekday()]
    return f"{wd} {dt.day:02d} de {SPANISH_MONTHS[dt.month-1]} {dt.year}"

class ReportAttendancePDF(models.AbstractModel):
    _name = 'report.custom_reports_mooch.attendance_pdf'
    _description = 'Asistencias PDF'

    def _process_attendance_data(self, events):
        """
        Procesa los datos de asistencia basado en el formato real de tuplas
        Formato: (datetime, 'in', location)
        """
        if not events:
            return {
                'entrada': '',
                'comida_ini': '',
                'comida_fin': '',
                'salida': '',
                'h_trab': '00:00',
                'h_comida': '00:00',
                'h_extra': '00:00'
            }
        
        # Ordenar eventos por fecha/hora
        sorted_events = sorted(events, key=lambda x: x[0])
        
        entrada = None
        salida = None
        comida_ini = None
        comida_fin = None
        
        # Analizar patrones basado en los horarios
        for i, event in enumerate(sorted_events):
            event_time = event[0]
            event_type = event[1]  # Siempre 'in' según los datos
            
            # Primera checada del día = entrada
            if i == 0:
                entrada = event_time
            
            # Última checada del día = salida
            if i == len(sorted_events) - 1:
                salida = event_time
            
            # Checadas entre 8:00-9:00 podrían ser inicio de comida
            if 8 <= event_time.hour <= 9 and comida_ini is None and i > 0:
                comida_ini = event_time
            
            # Checadas entre 13:00-15:00 podrían ser fin de comida
            if 13 <= event_time.hour <= 15 and comida_ini is not None and comida_fin is None:
                comida_fin = event_time
        
        # Si no se detectó comida, buscar patrones alternativos
        if not comida_ini and len(sorted_events) >= 3:
            # Patrón común: entrada, luego comida inicio, luego comida fin
            comida_ini = sorted_events[1][0] if len(sorted_events) > 1 else None
            comida_fin = sorted_events[2][0] if len(sorted_events) > 2 else None
        
        # Calcular horas trabajadas
        horas_trabajadas = 0
        horas_comida = 0
        horas_extra = 0
        
        if entrada and salida:
            horas_trabajadas = (salida - entrada).total_seconds()
            
            # Restar tiempo de comida si se detectó
            if comida_ini and comida_fin:
                horas_comida = (comida_fin - comida_ini).total_seconds()
                # Asegurar que el tiempo de comida sea razonable (máximo 2 horas)
                if 1800 <= horas_comida <= 7200:  # 30 min a 2 horas
                    horas_trabajadas -= horas_comida
                else:
                    horas_comida = 0
            
            # Horas extra (más de 8 horas)
            if horas_trabajadas > 8 * 3600:
                horas_extra = horas_trabajadas - 8 * 3600
            elif horas_trabajadas < 0:
                horas_trabajadas = 0

        return {
            'entrada': entrada.strftime('%H:%M') if entrada else '',
            'comida_ini': comida_ini.strftime('%H:%M') if comida_ini else '',
            'comida_fin': comida_fin.strftime('%H:%M') if comida_fin else '',
            'salida': salida.strftime('%H:%M') if salida else '',
            'h_trab': _fmt_hhmm_from_seconds(horas_trabajadas),
            'h_comida': _fmt_hhmm_from_seconds(horas_comida),
            'h_extra': _fmt_hhmm_from_seconds(horas_extra),
        }

    def _get_report_values(self, docids, data=None):
        wiz = self.env['attendance.report.wizard'].browse(docids)[:1]
        ds = wiz._fetch_dataset()

        cards = []
        for emp in ds.get('employees', []):
            filas = []
            emp_days = ds.get('per_emp_day', {}).get(emp.id, {})
            
            for d in ds.get('day_list', []):
                events_raw = emp_days.get(d, [])
                row = self._process_attendance_data(events_raw)

                # Determinar status
                is_workday = d.weekday() < 5
                has_attendance = row['entrada'] or row['salida']
                
                if not is_workday:
                    status = 'Descanso'
                elif has_attendance:
                    status = 'Asistencia'
                else:
                    status = 'Falta'

                filas.append({
                    'fecha_lbl': d.strftime('%a/%d/%b').lower(),
                    **row,
                    'status': status,
                })

            cards.append({
                'emp': emp,
                'dept': emp.department_id.name or '',
                'ref': emp.identification_id or emp.barcode or '',
                'rows': filas,
            })

        title = f"Registro de asistencia del {_title_spanish(ds['dfrom'])} al {_title_spanish(ds['dto'])}."
        cpp = 4

        return {
            'doc_ids': docids,
            'doc_model': 'attendance.report.wizard',
            'docs': wiz,
            'title': title,
            'cards': cards,
            'cards_per_page': cpp,
            'card_width': '48%',
            'include_signature': wiz.include_signature,
        }