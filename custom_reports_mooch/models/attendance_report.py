# -*- coding: utf-8 -*-
from odoo import models, fields
from datetime import datetime, date, timedelta
from collections import defaultdict
import pytz
import logging
_logger = logging.getLogger(__name__)

# ======= Constantes de formato =======
SPANISH_WEEKDAYS = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
SPANISH_MONTHS = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
DASH = '-'
GRACE_DAILY_SEC = 0

def _fmt_hhmm_from_seconds(seconds):
    if seconds is None or seconds == 0:
        return "00:00"  # CAMBIO: de "" a "00:00"
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h:02d}:{m:02d}"

def _title_spanish(dt):
    wd = SPANISH_WEEKDAYS[dt.weekday()]
    return f"{wd} {dt.day:02d} de {SPANISH_MONTHS[dt.month-1]} {dt.year}"

def _to_naive(dt):
    try:
        return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt
    except Exception:
        return dt

def _as_date(v):
    if isinstance(v, datetime):
        return v.date()
    return v

def _iter_days(dfrom, dto):
    d = dfrom
    while d <= dto:
        yield d
        d += timedelta(days=1)

class ReportAttendancePDF(models.AbstractModel):
    _name = 'report.custom_reports_mooch.attendance_pdf'
    _description = 'Asistencias PDF'

    # ---------- Descanso por empleado ----------
    def _is_rest_day(self, emp, d):
        dow = d.weekday()  # 0=Lun .. 6=Dom
        flags = {
            0: emp.rest_monday,
            1: emp.rest_tuesday,
            2: emp.rest_wednesday,
            3: emp.rest_thursday,
            4: emp.rest_friday,
            5: emp.rest_saturday,
            6: emp.rest_sunday,
        }
        if not any(flags.values()):
            return False
        return bool(flags.get(dow, False))

    # ---------- Obtener horario de comida desde Odoo ----------
    def _get_employee_lunch_schedule(self, emp, d):
        """
        Obtiene el horario de comida DEFINIDO en Odoo para el empleado
        Devuelve: (lunch_start, lunch_end) en datetime naive
        """
        cal = (
            getattr(emp, 'work_calendar_id', False)
            or emp.resource_calendar_id
            or emp.company_id.resource_calendar_id
            or self.env.company.resource_calendar_id
        )
        
        if not cal:
            _logger.warning("Empleado %s no tiene calendario asignado", emp.name)
            return (None, None)

        dow = str(d.weekday())
        lines = cal.attendance_ids.filtered(
            lambda l: l.dayofweek == dow and (not l.resource_id or l.resource_id == emp.resource_id)
        ).sorted(key=lambda l: l.hour_from)

        # Buscar segmento de comida/descanso
        lunch_segment = None
        for line in lines:
            name = (line.name or '').lower()
            wet = getattr(line, 'work_entry_type_id', False)
            wet_name = (wet and wet.name or '').lower()
            
            # Detectar si es segmento de comida
            is_lunch = (
                'comida' in name or 'almuerzo' in name or 'lunch' in name or
                'descanso' in name or 'break' in name or
                'comida' in wet_name or 'almuerzo' in wet_name or 'lunch' in wet_name or
                'descanso' in wet_name or 'break' in wet_name or
                getattr(line, 'is_break', False)
            )
            
            if is_lunch:
                lunch_segment = line
                break

        # Si no hay segmento explícito de comida, buscar el gap más grande entre segmentos de trabajo
        if not lunch_segment and len(lines) >= 2:
            work_segments = [l for l in lines if not self._is_break_line(l)]
            if len(work_segments) >= 2:
                # Encontrar el gap más grande entre segmentos de trabajo
                max_gap = timedelta(0)
                for i in range(len(work_segments) - 1):
                    gap_start = work_segments[i].hour_to
                    gap_end = work_segments[i + 1].hour_from
                    gap_duration = timedelta(hours=(gap_end - gap_start))  # CORRECCIÓN: Convertir a timedelta
                    if gap_duration > max_gap and gap_duration >= timedelta(minutes=30):  # CORRECCIÓN: Usar timedelta
                        max_gap = gap_duration
                        # Crear un segmento de comida ficticio
                        lunch_segment = type('obj', (object,), {
                            'hour_from': gap_start,
                            'hour_to': gap_end
                        })()

        if lunch_segment:
            # Convertir a datetime
            def _to_dt(hfloat):
                hh = int(hfloat)
                mm = int(round((hfloat - hh) * 60))
                return datetime(d.year, d.month, d.day, hh, mm)
            
            lunch_start = _to_dt(lunch_segment.hour_from)
            lunch_end = _to_dt(lunch_segment.hour_to)
            
            _logger.debug("Horario de comida para %s: %s a %s", 
                        emp.name, lunch_start.strftime('%H:%M'), lunch_end.strftime('%H:%M'))
            return (lunch_start, lunch_end)
        
        _logger.debug("No se encontró horario de comida para %s", emp.name)
        return (None, None)

    def _is_break_line(self, line):
        """Determina si una línea de attendance es de descanso/comida"""
        name = (line.name or '').lower()
        wet = getattr(line, 'work_entry_type_id', False)
        wet_name = (wet and wet.name or '').lower()
        
        return (
            'comida' in name or 'almuerzo' in name or 'lunch' in name or
            'descanso' in name or 'break' in name or
            'comida' in wet_name or 'almuerzo' in wet_name or 'lunch' in wet_name or
            'descanso' in wet_name or 'break' in wet_name or
            getattr(line, 'is_break', False)
        )

    # ---------- Hora esperada de entrada ----------
    def _expected_start_local(self, emp, d, is_rest_day):
        if is_rest_day:
            return None
        cal = (
            getattr(emp, 'work_calendar_id', False)
            or emp.resource_calendar_id
            or emp.company_id.resource_calendar_id
            or self.env.company.resource_calendar_id
        )
        if not cal:
            return None

        dow = str(d.weekday())  # 0..6
        lines = cal.attendance_ids.filtered(
            lambda l: l.dayofweek == dow and (not l.resource_id or l.resource_id == emp.resource_id)
        )
        if not lines:
            return None

        # Buscar primera hora de entrada (excluyendo breaks)
        work_lines = [l for l in lines if not self._is_break_line(l)]
        if not work_lines:
            return None

        hour = min(work_lines, key=lambda x: x.hour_from).hour_from
        hh = int(hour)
        mm = int(round((hour - hh) * 60))
        return datetime(d.year, d.month, d.day, hh, mm)


    def _planned_lunch_window(self, emp, d):
        """
        Devuelve (lunch_start_dt, lunch_end_dt) en hora local NAIVE, si el
        calendario del empleado tiene un tramo marcado como Descanso/Comida.
        """
        cal = (
            getattr(emp, 'work_calendar_id', False)
            or emp.resource_calendar_id
            or emp.company_id.resource_calendar_id
            or self.env.company.resource_calendar_id
        )
        if not cal:
            return (None, None)

        dow = str(d.weekday())
        lines = cal.attendance_ids.filtered(
            lambda l: l.dayofweek == dow and (not l.resource_id or l.resource_id == emp.resource_id)
        )
        if not lines:
            return (None, None)

        def _is_break(l):
            name = (l.name or '').lower()
            wet  = getattr(l, 'work_entry_type_id', False)
            wetn = (wet and wet.name or '').lower()
            return (
                'descanso' in name or 'comida' in name or 'almuerzo' in name or
                'lunch' in name   or 'break' in name or
                'descanso' in wetn or 'comida' in wetn or 'almuerzo' in wetn or
                'lunch' in wetn or 'break' in wetn or
                bool(getattr(l, 'is_break', False))
            )

        breaks = [l for l in lines if _is_break(l)]
        if not breaks:
            return (None, None)

        start = min(b.hour_from for b in breaks)
        end   = max(b.hour_to   for b in breaks)

        def _to_dt(hfloat):
            hh = int(hfloat)
            mm = int(round((hfloat - hh) * 60))
            return datetime(d.year, d.month, d.day, hh, mm)

        return (_to_dt(start), _to_dt(end))

    def _planned_segments(self, emp, d):
        """
        Devuelve lista de segmentos planeados para el día con mejor logging
        """
        cal = (
            getattr(emp, 'work_calendar_id', False)
            or emp.resource_calendar_id
            or emp.company_id.resource_calendar_id
            or self.env.company.resource_calendar_id
        )
        
        if not cal:
            _logger.debug("Empleado %s no tiene calendario asignado", emp.name)
            return []

        dow = str(d.weekday())
        lines = cal.attendance_ids.filtered(
            lambda l: l.dayofweek == dow and (not l.resource_id or l.resource_id == emp.resource_id)
        ).sorted(key=lambda l: l.hour_from)

        _logger.debug("Calendario para %s - Día %s: %s líneas", emp.name, d, len(lines))

        def _is_break(l):
            name = (l.name or '').lower()
            wet  = getattr(l, 'work_entry_type_id', False)
            wetn = (wet and wet.name or '').lower()
            is_break = (
                'descanso' in name or 'comida' in name or 'almuerzo' in name or
                'lunch' in name or 'break' in name or
                'descanso' in wetn or 'comida' in wetn or 'almuerzo' in wetn or
                'lunch' in wetn or 'break' in wetn or
                bool(getattr(l, 'is_break', False))
            )
            _logger.debug("Línea %s-%s: %s (break=%s)", l.hour_from, l.hour_to, l.name, is_break)
            return is_break

        def _to_dt(hfloat):
            hh = int(hfloat)
            mm = int(round((hfloat - hh) * 60))
            return datetime(d.year, d.month, d.day, hh, mm)

        segs = []
        for l in lines:
            seg_kind = 'break' if _is_break(l) else 'work'
            segs.append({
                'kind': seg_kind,
                'start': _to_dt(l.hour_from),
                'end':   _to_dt(l.hour_to),
                'name':  l.name or '',
            })
            _logger.debug("Segmento: %s %s-%s (%s)", seg_kind, 
                        _to_dt(l.hour_from).strftime('%H:%M'), 
                        _to_dt(l.hour_to).strftime('%H:%M'), 
                        l.name or 'sin nombre')

        return segs

    def _classify_events_by_schedule(self, events, planned_segments, emp, d):
        """
        Clasifica los eventos en: entrada_principal, salida_principal, comida_salida, comida_entrada, overtime
        basándose en los segmentos planeados del calendario del empleado.
        """
        if not events or not planned_segments:
            return [], [], [], [], []

        # Obtener segmentos de trabajo (no break)
        work_segments = [s for s in planned_segments if s['kind'] == 'work']
        break_segments = [s for s in planned_segments if s['kind'] == 'break']
        
        # Determinar ventana de comida principal
        lunch_window = None
        if break_segments:
            lunch_window = (break_segments[0]['start'], break_segments[0]['end'])
        elif len(work_segments) >= 2:
            # Si hay múltiples segmentos de trabajo, el gap más grande es probablemente la comida
            max_gap = timedelta(0)
            for i in range(len(work_segments) - 1):
                gap = work_segments[i+1]['start'] - work_segments[i]['end']
                if gap > max_gap and gap >= timedelta(minutes=30):
                    max_gap = gap
                    lunch_window = (work_segments[i]['end'], work_segments[i+1]['start'])

        # Clasificar eventos
        main_ins = []
        main_outs = []
        lunch_outs = []
        lunch_ins = []
        overtime_events = []

        TOLERANCE = timedelta(minutes=30)  # Tolerancia para considerar dentro de segmento
        
        for event_dt, event_type in events:
            if not event_dt:
                continue
                
            # Determinar a qué segmento pertenece este evento
            in_work_segment = False
            in_break_segment = False
            is_overtime = True  # Por defecto asumimos overtime hasta probar lo contrario
            
            # Verificar si está en algún segmento de trabajo
            for seg in work_segments:
                start_with_tol = seg['start'] - TOLERANCE
                end_with_tol = seg['end'] + TOLERANCE
                if start_with_tol <= event_dt <= end_with_tol:
                    in_work_segment = True
                    is_overtime = False
                    break
            
            # Verificar si está en segmento de break
            if not in_work_segment and lunch_window:
                start_with_tol = lunch_window[0] - TOLERANCE
                end_with_tol = lunch_window[1] + TOLERANCE
                if start_with_tol <= event_dt <= end_with_tol:
                    in_break_segment = True
                    is_overtime = False

            # Clasificar según tipo de evento y segmento
            if event_type in ['in', 0]:
                if in_work_segment and event_dt.time() <= (lunch_window[0].time() if lunch_window else datetime.max.time()):
                    main_ins.append(event_dt)
                elif in_break_segment:
                    lunch_ins.append(event_dt)
                elif is_overtime:
                    overtime_events.append((event_dt, 'in'))
                    
            elif event_type in ['out', 1]:
                if in_work_segment and event_dt.time() >= (lunch_window[1].time() if lunch_window else datetime.min.time()):
                    main_outs.append(event_dt)
                elif in_break_segment:
                    lunch_outs.append(event_dt)
                elif is_overtime:
                    overtime_events.append((event_dt, 'out'))
                    
            elif event_type in ['lunch_out', 4]:
                lunch_outs.append(event_dt)
            elif event_type in ['lunch_in', 5]:
                lunch_ins.append(event_dt)

        # Ordenar todos los eventos
        main_ins.sort()
        main_outs.sort()
        lunch_outs.sort()
        lunch_ins.sort()
        overtime_events.sort(key=lambda x: x[0])

        return main_ins, main_outs, lunch_outs, lunch_ins, overtime_events

    # ---------- Normalización de eventos ----------
    def _normalize_events(self, events):
        """
        Acepta:
          - [(datetime, 'in'|'out'|str|int, ...), ...]
          - [datetime, datetime, ...] → alterna in/out
        Mapa: 0→in, 1→out, 4→out (inicio comida), 5→in (fin comida)
              'check in'/'overtime in' → in ; 'check out'/'overtime out' → out
        Devuelve: [(dt_naive, 'in'|'out'), ...] ordenados.
        """
        map_int = {0: 'in', 1: 'out', 4: 'out', 5: 'in'}
        in_strs  = {'in', 'check in', 'check_in', 'overtime in', 'overtime_in'}
        out_strs = {'out', 'check out', 'check_out', 'overtime out', 'overtime_out'}

        norm = []
        for e in events:
            if isinstance(e, (list, tuple)):
                dt = e[0]
                typ = e[1] if len(e) > 1 else None
            else:  # solo datetime
                dt = e
                typ = None

            tnorm = None
            if isinstance(typ, int):
                tnorm = map_int.get(typ)
            elif typ is not None:
                s = str(typ).strip().lower()
                if s in in_strs:
                    tnorm = 'in'
                elif s in out_strs:
                    tnorm = 'out'

            norm.append((_to_naive(dt), tnorm))

        # Orden cronológico
        norm.sort(key=lambda x: x[0])

        # Si los tipos vienen "cojos" (todos iguales o todos None), alternar por orden
        has_in = any(t == 'in' for _, t in norm)
        has_out = any(t == 'out' for _, t in norm)
        if not (has_in and has_out):
            return [(dt, 'in' if i % 2 == 0 else 'out') for i, (dt, _) in enumerate(norm)]

        # Caso mixto: rellenar missing alternando desde el último conocido
        filled, current = [], 'in'
        for dt, t in norm:
            if t in ('in', 'out'):
                current = t
            else:
                t = current
            filled.append((dt, t))
            current = 'out' if t == 'in' else 'in'
        return filled
    # ---------- Ventanas (intervalos) programadas según el calendario ----------
    def _get_day_windows(self, emp, d):
        """
        Devuelve una lista de intervalos [(start_dt, end_dt), ...] en hora local (naive)
        a partir del calendario del empleado para el día d.
        Si el calendario tiene 2+ intervalos, el hueco mayor suele ser la comida.
        """
        cal = (
            getattr(emp, 'work_calendar_id', False)
            or emp.resource_calendar_id
            or emp.company_id.resource_calendar_id
            or self.env.company.resource_calendar_id
        )
        if not cal:
            return []

        dow = str(d.weekday())  # '0'..'6'
        lines = cal.attendance_ids.filtered(
            lambda l: l.dayofweek == dow and (not l.resource_id or l.resource_id == emp.resource_id)
        )
        if not lines:
            return []

        intervals = []
        for l in sorted(lines, key=lambda x: x.hour_from):
            hf = float(l.hour_from or 0.0)
            ht = float(l.hour_to or 0.0)
            fh, fm = int(hf), int(round((hf - int(hf)) * 60))
            th, tm = int(ht), int(round((ht - int(ht)) * 60))
            start = datetime(d.year, d.month, d.day, fh, fm)
            end   = datetime(d.year, d.month, d.day, th, tm)
            if end > start:
                intervals.append((start, end))
        return intervals

    # ---------- Cálculo por día ----------
    # ---------- Procesamiento CON DEBUG DETALLADO ----------
    def _process_attendance_data(self, events_raw, expected_start, is_rest, planned_lunch=None, planned_segments=None, emp=None, d=None):
        """
        Versión que detecta comidas con Overtime In/Out Y Check In/Out dentro del horario de comida
        Y usa horario de Odoo cuando no hay salida en biometrico
        """
        print(f"=== _process_attendance_data PARA {emp.name if emp else 'None'} - {d} ===")
        print(f"events_raw recibidos: {len(events_raw)} eventos")

        # Función para convertir a naive si es necesario
        def to_naive(dt):
            if dt and dt.tzinfo is not None:
                return dt.replace(tzinfo=None)
            return dt

        # Clasificar eventos
        check_ins, check_outs, lunch_outs, lunch_ins = [], [], [], []
        all_events = []  # Para todos los eventos

        for event in events_raw:
            if isinstance(event, (list, tuple)) and len(event) >= 2:
                dt, punch_type = event[0], event[1]
                dt = to_naive(dt)
                print(f"Evento: {dt.strftime('%H:%M')} - {punch_type}")

                all_events.append((dt, punch_type))

                if punch_type == 'in':
                    check_ins.append(dt)
                elif punch_type == 'out':
                    check_outs.append(dt)
                elif punch_type == 'lunch_out':
                    lunch_outs.append(dt)
                elif punch_type == 'lunch_in':
                    lunch_ins.append(dt)

        # Ordenar
        check_ins.sort()
        check_outs.sort()
        lunch_outs.sort()
        lunch_ins.sort()
        all_events.sort(key=lambda x: x[0])

        # Tomar valores principales
        entrada = check_ins[0] if check_ins else None
        salida = check_outs[-1] if check_outs else None

        # ===== NUEVA LÓGICA: Obtener salida estimada del horario de Odoo =====
        salida_estimada = None
        if not salida and entrada:  # Solo si hay entrada pero no salida en biometrico
            print("No hay salida en biometrico, buscando horario programado en Odoo...")

            # Obtener horario programado del empleado
            cal = (
                getattr(emp, 'work_calendar_id', False)
                or emp.resource_calendar_id
                or emp.company_id.resource_calendar_id
                or self.env.company.resource_calendar_id
            )

            if cal:
                dow = str(d.weekday())
                lines = cal.attendance_ids.filtered(
                    lambda l: l.dayofweek == dow and (not l.resource_id or l.resource_id == emp.resource_id)
                ).sorted(key=lambda l: l.hour_from)

                # Buscar última hora de salida (excluyendo breaks)
                work_lines = [l for l in lines if not self._is_break_line(l)]
                if work_lines:
                    # Tomar la última hora de salida del día
                    last_work_line = max(work_lines, key=lambda x: x.hour_to)
                    hour_out = last_work_line.hour_to
                    hh = int(hour_out)
                    mm = int(round((hour_out - hh) * 60))
                    salida_estimada = datetime(d.year, d.month, d.day, hh, mm)
                    print(f"Salida estimada desde Odoo: {salida_estimada.strftime('%H:%M')}")

            # Si no se encontró horario, usar una salida por defecto (ej: 6 horas después de la entrada)
            if not salida_estimada and entrada:
                salida_estimada = entrada + timedelta(hours=6)
                print(f"Salida estimada por defecto (6hrs después): {salida_estimada.strftime('%H:%M')}")

        # Usar salida del biometrico si existe, si no usar la estimada
        salida_final = salida if salida else salida_estimada
        print(f"Salida final: {salida_final.strftime('%H:%M') if salida_final else 'No disponible'}")

        # ===== DETECCIÓN MEJORADA DE COMIDA =====
        comida_ini = None
        comida_fin = None

        # Obtener horario de comida de Odoo
        lunch_start, lunch_end = self._get_employee_lunch_schedule(emp, d)

        # Solo procesar comidas si hay horario de Odoo
        if lunch_start and lunch_end:
            print(f"Horario comida Odoo: {lunch_start.strftime('%H:%M')} a {lunch_end.strftime('%H:%M')}")

            # Crear ventana de tolerancia (±60 minutos)
            tolerance = timedelta(minutes=60)
            window_start = lunch_start - tolerance
            window_end = lunch_end + tolerance

            print(f"Ventana comida con tolerancia: {window_start.strftime('%H:%M')} a {window_end.strftime('%H:%M')}")

            # Buscar TODOS los eventos dentro de la ventana de comida
            events_in_lunch_window = []
            for dt, punch_type in all_events:
                if window_start <= dt <= window_end:
                    events_in_lunch_window.append((dt, punch_type))

            print(f"Eventos en ventana comida: {len(events_in_lunch_window)}")
            for dt, pt in events_in_lunch_window:
                print(f"  - {dt.strftime('%H:%M')} - {pt}")

            # Separar eventos de comida explícitos (Overtime) y eventos regulares (Check In/Out)
            explicit_lunch_outs = [dt for dt, pt in events_in_lunch_window if pt == 'lunch_out']
            explicit_lunch_ins = [dt for dt, pt in events_in_lunch_window if pt == 'lunch_in']
            check_ins_in_window = [dt for dt, pt in events_in_lunch_window if pt == 'in']
            check_outs_in_window = [dt for dt, pt in events_in_lunch_window if pt == 'out']

            print(f"Explicit lunch outs: {[dt.strftime('%H:%M') for dt in explicit_lunch_outs]}")
            print(f"Explicit lunch ins: {[dt.strftime('%H:%M') for dt in explicit_lunch_ins]}")
            print(f"Check ins en ventana: {[dt.strftime('%H:%M') for dt in check_ins_in_window]}")
            print(f"Check outs en ventana: {[dt.strftime('%H:%M') for dt in check_outs_in_window]}")

            # PRIORIDAD 1: Eventos explícitos de comida (Overtime In/Out)
            if explicit_lunch_outs or explicit_lunch_ins:
                print("Usando eventos explícitos de comida")

                # CASO 1: Hay ambos tipos (Overtime In y Overtime Out)
                if explicit_lunch_outs and explicit_lunch_ins:
                    comida_ini = min(explicit_lunch_outs)
                    comida_fin = max(explicit_lunch_ins)
                    print("Caso 1: Ambos tipos explícitos encontrados")

                # CASO 2: Solo hay Overtime In (múltiples)
                elif explicit_lunch_outs and not explicit_lunch_ins:
                    comida_ini = min(explicit_lunch_outs)

                    if len(explicit_lunch_outs) >= 2:
                        comida_fin = max(explicit_lunch_outs)
                        print("Caso 2: Múltiples Overtime In, usando último como fin")
                    else:
                        print("Caso 2: Un solo Overtime In, sin fin de comida")

                # CASO 3: Solo hay Overtime Out (raro)
                elif explicit_lunch_ins and not explicit_lunch_outs:
                    comida_fin = max(explicit_lunch_ins)
                    print("Caso 3: Solo Overtime Out, solo fin de comida")

                # CASO 4: NUEVO - Hay Overtime Out Y Check Out dentro del horario de comida
                if explicit_lunch_ins and check_outs_in_window:
                    print("Caso 4: Overtime Out y Check Out en ventana de comida detectados")

                    # Tomar el Overtime Out como Overtime In (inicio de comida)
                    comida_ini = min(explicit_lunch_ins)
                    print(f"Overtime Out tratado como Overtime In: {comida_ini.strftime('%H:%M')}")

                    # Tomar el Check Out como Overtime Out (fin de comida)
                    comida_fin = max(check_outs_in_window)
                    print(f"Check Out tratado como Overtime Out: {comida_fin.strftime('%H:%M')}")

            # PRIORIDAD 2: Eventos regulares (Check In/Out) dentro del horario de comida
            elif check_ins_in_window or check_outs_in_window:
                print("Usando Check In/Out como eventos de comida")

                # Si hay Check In/Out en la ventana, tratarlos como comida
                if check_ins_in_window:
                    comida_ini = min(check_ins_in_window)
                    print(f"Check In como inicio comida: {comida_ini.strftime('%H:%M')}")

                if check_outs_in_window:
                    comida_fin = max(check_outs_in_window)
                    print(f"Check Out como fin comida: {comida_fin.strftime('%H:%M')}")

                # Si tenemos inicio pero no fin, buscar el siguiente evento después del inicio
                if comida_ini and not comida_fin:
                    for dt, pt in all_events:
                        if dt > comida_ini and window_start <= dt <= window_end:
                            comida_fin = dt
                            print(f"Usando siguiente evento como fin: {comida_fin.strftime('%H:%M')}")
                            break

            # PRIORIDAD 3: No hay eventos en la ventana - dejar vacío
            else:
                print("No hay eventos en la ventana de comida - dejar vacío")

            # Validar que la comida sea razonable (solo si tenemos ambos)
            if comida_ini and comida_fin:
                if comida_fin <= comida_ini:
                    # Si el fin es antes del inicio, solo mostrar inicio
                    comida_fin = None
                    print("Comida inválida (fin <= inicio), mostrando solo inicio")

                # Ajustar si se sale del rango laboral
                if entrada and comida_ini < entrada:
                    comida_ini = entrada
                if salida_final and comida_fin and comida_fin > salida_final:
                    comida_fin = salida_final
        else:
            print("No hay horario de comida definido en Odoo - dejar vacío")

        # Formatear - CAMBIO AQUÍ: Usar DASH cuando no hay datos
        def fmt(dt):
            return dt.strftime('%H:%M') if dt else DASH  # Cambiado de '' a DASH

        print(f"Check Ins: {[fmt(dt) for dt in check_ins]}")
        print(f"Check Outs: {[fmt(dt) for dt in check_outs]}")
        print(f"Lunch Outs (Overtime In): {[fmt(dt) for dt in lunch_outs]}")
        print(f"Lunch Ins (Overtime Out): {[fmt(dt) for dt in lunch_ins]}")
        print(f"RESULTADO: entrada={fmt(entrada)}, comida_ini={fmt(comida_ini)}, comida_fin={fmt(comida_fin)}, salida={fmt(salida_final)}")
        print("==========================================")

        expected_start_naive = to_naive(expected_start)

        work_secs, lunch_secs = 0, 0

        # CALCULAR HORAS TRABAJADAS CON SALIDA FINAL (que puede ser estimada)
        if entrada and salida_final and salida_final > entrada:
            total_secs = int((salida_final - entrada).total_seconds())

            if comida_ini and comida_fin:
                lunch_start_in_range = max(comida_ini, entrada)
                lunch_end_in_range = min(comida_fin, salida_final)
                if lunch_end_in_range > lunch_start_in_range:
                    lunch_secs = int((lunch_end_in_range - lunch_start_in_range).total_seconds())

            work_secs = max(0, total_secs - lunch_secs)

        retardo_sec = 0
        if not is_rest and entrada and expected_start_naive and entrada > expected_start_naive:
            retardo_sec = int((entrada - expected_start_naive).total_seconds())
            retardo_sec = (retardo_sec // 60) * 60

        # CAMBIO AQUÍ: Formatear tiempos para mostrar "00:00" cuando no hay datos
        def format_time(seconds):
            if not seconds or seconds <= 0:
                return "00:00"  # Cambiado de '' a "00:00"
            return f"{int(seconds//3600):02d}:{int((seconds%3600)//60):02d}"

        return {
            'entrada': fmt(entrada),
            'comida_ini': fmt(comida_ini),
            'comida_fin': fmt(comida_fin),
            'salida': fmt(salida_final),  # Usar salida_final que puede ser estimada
            'h_trab': format_time(work_secs),
            'h_comida': format_time(lunch_secs),
            'h_extra': '',
            'retardo': format_time(retardo_sec),
            'retardo_sec': retardo_sec,
            'has_attendance': bool(entrada or salida_final),
            'salida_estimada': salida_final and not salida,  # Indicar si la salida es estimada
        }

    # ---------- Índice de ausencias (hr.leave) por día ----------
    def _build_leave_index(self, emp, dfrom, dto):
        dfrom_d = _as_date(dfrom)
        dto_d = _as_date(dto)

        Leave = self.env['hr.leave']
        leaves = Leave.search([
            ('employee_id', '=', emp.id),
            ('state', 'not in', ['cancel', 'refuse']),
            ('request_date_from', '<=', dto_d),
            ('request_date_to', '>=', dfrom_d),
        ])

        idx = {}
        for lv in leaves:
            start = lv.request_date_from or _as_date(lv.date_from)
            end = lv.request_date_to or _as_date(lv.date_to)
            start = _as_date(start)
            end = _as_date(end)
            if not start or not end:
                continue
            start = max(start, dfrom_d)
            end = min(end, dto_d)
            for dd in _iter_days(start, end):
                idx[dd] = lv
        return idx

    # Dentro de class ReportAttendancePDF(models.AbstractModel):

    def _build_events_index_from_attendance(self, emp, dfrom, dto):
        """
        Construye un índice por día con checadas a partir de hr.attendance
        cuando el dataset no trae per_emp_day.
        Devuelve: { date: [(datetime, 'in'|'out'), ...] }
        """
        Att = self.env['hr.attendance']

        dfrom_d = _as_date(dfrom)
        dto_d   = _as_date(dto)

        # Rango completo del periodo en datetime
        dt_start = datetime.combine(dfrom_d, datetime.min.time())
        dt_end   = datetime.combine(dto_d,   datetime.max.time())

        domain = [
            ('employee_id', '=', emp.id),
            ('check_in', '<=', dt_end),
            '|', ('check_out', '=', False), ('check_out', '>=', dt_start),
        ]
        recs = Att.search(domain, order='check_in asc')

        from collections import defaultdict
        events_by_day = defaultdict(list)

        tz = pytz.timezone(self.env.user.tz or 'UTC')

        def _loc(dt):
            if not dt:
                return None
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            return dt.astimezone(tz)

        for att in recs:
            if att.check_in:
                ci = _loc(att.check_in)
                events_by_day[ci.date()].append((ci, 'in'))
            if att.check_out:
                co = _loc(att.check_out)
                events_by_day[co.date()].append((co, 'out'))

        return events_by_day


    # ---------- Armado del reporte ----------
    def _get_report_values(self, docids, data=None):
        _logger.info("=== INICIANDO GENERACIÓN DE REPORTE ===")
        
        try:
            # --- 1) Obtener dataset ---
            wiz = self.env['attendance.report.wizard'].browse(docids)[:1]
            ds = None
            if data and isinstance(data, dict) and data.get('form'):
                ds = data['form']
                _logger.info("Dataset obtenido desde data['form']")
            else:
                _logger.info("Obteniendo dataset desde wizard...")
                ds = wiz._fetch_dataset()

            # --- Helpers de normalización ---
            def _as_dt(v):
                if v is None:
                    return None
                if isinstance(v, datetime):
                    return v
                if isinstance(v, str):
                    try:
                        return fields.Datetime.from_string(v)
                    except Exception:
                        try:
                            return datetime.fromisoformat(v)
                        except Exception:
                            return None
                return v

            def _as_date(v):
                if v is None:
                    return None
                if isinstance(v, date) and not isinstance(v, datetime):
                    return v
                if isinstance(v, datetime):
                    return v.date()
                if isinstance(v, str):
                    try:
                        return fields.Date.from_string(v)
                    except Exception:
                        try:
                            return datetime.fromisoformat(v).date()
                        except Exception:
                            return None
                return v

            def _iter_days(d1, d2):
                cur = d1
                while cur <= d2:
                    yield cur
                    cur += timedelta(days=1)

            # dfrom/dto
            dfrom = _as_dt(ds.get('dfrom'))
            dto   = _as_dt(ds.get('dto'))

            # employees
            emp_val = ds.get('employees')
            if getattr(emp_val, 'ids', False):
                employees = list(emp_val)
            elif isinstance(emp_val, (list, tuple, set)) and emp_val and isinstance(next(iter(emp_val)), int):
                employees = list(self.env['hr.employee'].browse(list(emp_val)))
            else:
                employees = list(self.env['hr.employee'].search([('active', '=', True)], limit=10))

            # day_list
            raw_days = ds.get('day_list')
            if raw_days:
                day_list = [_as_date(d) for d in raw_days]
                day_list = [d for d in day_list if d]
            else:
                day_list = list(_iter_days(_as_date(dfrom), _as_date(dto)))

            # per_emp_day
            per_emp_day_all = ds.get('per_emp_day', {}) or {}
            norm_per_emp = {}
            for emp_key, day_map in per_emp_day_all.items():
                try:
                    emp_id_int = int(emp_key)
                except Exception:
                    emp_id_int = emp_key
                new_day_map = {}
                if isinstance(day_map, dict):
                    for k, events in day_map.items():
                        kd = _as_date(k)
                        fixed_events = []
                        if isinstance(events, (list, tuple)):
                            for ev in events:
                                if isinstance(ev, (list, tuple)) and ev:
                                    t = _as_dt(ev[0])
                                    typ = ev[1] if len(ev) > 1 else None
                                    fixed_events.append((t, typ))
                        new_day_map[kd] = fixed_events
                norm_per_emp[emp_id_int] = new_day_map

            _logger.info("Procesando %s empleados, %s días", len(employees), len(day_list))

            # --- 2) Armado de tarjetas ---
            cards = []
            THRESH_WEEK_SEC = 10 * 60  # 10 minutos acumulables/semana

            for emp in employees:
                filas_tmp = []

                emp_days = norm_per_emp.get(emp.id)
                # Fallback: si no hay datos del checador para el empleado, arma desde hr.attendance
                if not emp_days:
                    emp_days = self._build_events_index_from_attendance(emp, dfrom, dto)

                # Índice de ausencias
                leave_idx = self._build_leave_index(emp, dfrom, dto)

                for d in day_list:
                    is_rest = self._is_rest_day(emp, d)
                    expected_start = self._expected_start_local(emp, d, is_rest)

                    # Segs planeados
                    segs = self._planned_segments(emp, d)

                    # Detectar break planeado
                    lunch_seg = None
                    for s in segs:
                        if s.get('kind') == 'break':
                            lunch_seg = (s['start'], s['end'])
                            break
                    if not lunch_seg and len(segs) >= 2:
                        max_gap = timedelta(0)
                        for i in range(len(segs) - 1):
                            if segs[i]['kind'] == 'work' and segs[i + 1]['kind'] == 'work':
                                gap = segs[i + 1]['start'] - segs[i]['end']
                                if gap > max_gap and gap >= timedelta(minutes=30):
                                    max_gap = gap
                                    lunch_seg = (segs[i]['end'], segs[i + 1]['start'])

                    # Eventos del día
                    events_raw = []
                    if emp_days and d in emp_days:
                        # Ahora events_raw vendrá en formato [(datetime, tipo)]
                        events_raw = emp_days[d]
                        print(f"Eventos para {emp.name} - {d}: {len(events_raw)} eventos")
                        for event_time, event_type in events_raw:
                            print(f"  - {event_time.strftime('%H:%M')} - {event_type}")
                    
                    row = self._process_attendance_data(
                        events_raw, expected_start, is_rest,
                        planned_lunch=lunch_seg,
                        planned_segments=segs,
                        emp=emp,
                        d=d
                    )

                    # Determinar status
                    has_attendance = row.pop('has_attendance', None)
                    if has_attendance is None:
                        def _nz(x):
                            s = '' if x is None else str(x).strip()
                            return bool(s) and s not in ('00:00', DASH, '—', '--')
                        has_attendance = _nz(row.get('entrada')) or _nz(row.get('salida')) \
                                        or _nz(row.get('comida_ini')) or _nz(row.get('comida_fin'))

                    # Status base
                    if is_rest:
                        status = 'Descanso'
                        row['retardo'] = '00:00'
                        row['retardo_sec'] = 0
                        row.update({
                            'entrada': DASH, 'comida_ini': DASH, 'comida_fin': DASH, 'salida': DASH,
                            'h_trab': DASH, 'h_comida': DASH, 'h_extra': DASH,
                        })
                    else:
                        if has_attendance:
                            status = 'Asistencia'
                            if int(row.get('retardo_sec', 0)) > GRACE_DAILY_SEC:
                                status = 'Retardo'
                        else:
                            status = 'Falta'
                            row.update({
                                'entrada': DASH, 'comida_ini': DASH, 'comida_fin': DASH, 'salida': DASH,
                                'h_trab': DASH, 'h_comida': DASH, 'h_extra': DASH,
                                'retardo': '00:00', 'retardo_sec': 0,
                            })

                    # Si hay leave ese día, predomina
                    leave = leave_idx.get(_as_date(d))
                    if leave:
                        status = leave.holiday_status_id.name or 'Tiempo libre'
                        row.update({
                            'entrada': DASH, 'comida_ini': DASH, 'comida_fin': DASH, 'salida': DASH,
                            'h_trab': DASH, 'h_comida': DASH, 'h_extra': DASH,
                            'retardo': '00:00', 'retardo_sec': 0,
                        })

                    filas_tmp.append({
                        'd': d,
                        'week_key': (d.isocalendar().year, d.isocalendar().week),
                        'fecha_lbl': d.strftime('%a/%d/%b').lower(),
                        'is_rest': is_rest,
                        'has_attendance': has_attendance,
                        **row,
                        'status': status,
                    })

                # Acumulado semanal de retardos
                from collections import defaultdict
                sum_week = defaultdict(int)
                for r in filas_tmp:
                    if not r['is_rest'] and r['has_attendance']:
                        sum_week[r['week_key']] += r.get('retardo_sec', 0)

                # Total de retardo del periodo
                retardo_total_sec = sum(
                    r.get('retardo_sec', 0)
                    for r in filas_tmp
                    if not r['is_rest'] and r['has_attendance']
                )

                # Normaliza filas para salida
                filas = []
                for r in filas_tmp:
                    if r['status'] == 'Asistencia' and r.get('retardo_sec', 0) > 0:
                        if sum_week[r['week_key']] > THRESH_WEEK_SEC:
                            r['status'] = 'Retardo'
                    for k in ('retardo_sec', 'd', 'week_key', 'is_rest', 'has_attendance'):
                        r.pop(k, None)
                    filas.append(r)

                cards.append({
                    'emp': emp,
                    'dept': emp.department_id.name or '',
                    'ref': emp.barcode or emp.identification_id or 'no asignado',
                    'suc': getattr(emp, 'work_location_id', False) and emp.work_location_id.name or 'no asignada',
                    'retardo_total': _fmt_hhmm_from_seconds(retardo_total_sec),
                    'rows': filas,
                })

            # --- 3) Preparar variables para el template ---
            tzname = ds.get('tz') or 'UTC'
            try:
                tz = pytz.timezone(tzname)
            except Exception:
                tz = pytz.timezone('UTC')

            def _to_local(dt):
                if dt is None:
                    return None
                aware = pytz.utc.localize(dt) if getattr(dt, 'tzinfo', None) is None else dt.astimezone(pytz.UTC)
                return aware.astimezone(tz)

            start_local = _to_local(dfrom)
            end_local   = _to_local(dto)

            first_date_formatted = _title_spanish(start_local)
            last_date_formatted  = _title_spanish(end_local)

            title = f"Registro de asistencia del {first_date_formatted} al {last_date_formatted}."
            cpp = 4  # cards per page
            card_width = '48%'

            _logger.info("=== REPORTE GENERADO EXITOSAMENTE ===")
            _logger.info("Cards: %s, Cards por página: %s", len(cards), cpp)

            return {
                'doc_ids': docids,
                'doc_model': 'attendance.report.wizard',
                'docs': wiz,
                'title': title,
                'cards': cards,
                'cards_per_page': cpp,
                'card_width': card_width,
                'include_signature': bool(ds.get('include_signature', True)),
                'first_date_formatted': first_date_formatted,
                'last_date_formatted': last_date_formatted,
            }

        except Exception as e:
            _logger.error("ERROR en _get_report_values: %s", str(e))
            raise

# Asegurar que la función _fmt_hhmm_from_seconds esté disponible
ReportAttendancePDF._fmt_hhmm_from_seconds = _fmt_hhmm_from_seconds
