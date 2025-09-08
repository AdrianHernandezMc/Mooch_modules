# -*- coding: utf-8 -*-
from odoo import models
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
    if seconds is None:
        seconds = 0
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

        hour = min(lines.mapped('hour_from'))  # p.ej. 9.5 = 09:30
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
        
        import logging
        _logger = logging.getLogger(__name__)
        
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
    def _process_attendance_data(self, events_raw, expected_start, is_rest, planned_lunch=None, planned_segments=None):
        """
        Maneja múltiples checadas y prioriza checadas reales.
        FIX: si no hay 'in', ya NO usar la primera marca como entrada;
            primero intentaremos completar desde hr.attendance (ver paso 2 abajo).
        """
        from datetime import timedelta
        import logging

        logger = logging.getLogger('attendance_debug')
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        def hhmm(total_secs):
            total_secs = max(0, int(total_secs or 0))
            h = total_secs // 3600
            m = (total_secs % 3600) // 60
            return f"{h:02d}:{m:02d}"

        fmt = lambda dt: dt.strftime('%H:%M') if dt else '00:00'

        logger.debug("=== INICIANDO PROCESAMIENTO DE ASISTENCIA ===")
        logger.debug("Eventos crudos recibidos: %s", events_raw)

        # --- Regla: en domingo NO se contabiliza comida ---
        is_sunday = False
        _ref = None
        if events_raw:
            _ref = events_raw[0][0]
        elif planned_segments:
            _ref = planned_segments[0].get('start')
        elif expected_start:
            _ref = expected_start
        if _ref:
            try:
                is_sunday = (_ref.weekday() == 6)  # 6 = Domingo
            except Exception:
                is_sunday = False

        # --- PASO 1: Separar checadas por tipo ---
        all_events = []
        lunch_out_events = []
        lunch_in_events = []
        in_events = []
        out_events = []

        for dt, p in events_raw:
            if dt:
                all_events.append((dt, p))
                if p == 'lunch_out':
                    if not is_sunday:
                        lunch_out_events.append(dt)
                elif p == 'lunch_in':
                    if not is_sunday:
                        lunch_in_events.append(dt)
                elif p == 'in':
                    in_events.append(dt)
                elif p == 'out':
                    out_events.append(dt)

        all_events.sort(key=lambda x: x[0])
        all_times = [dt for dt, p in all_events]

        logger.debug("Todos los eventos: %s", [(dt.strftime('%H:%M'), p) for dt, p in all_events])
        logger.debug("Eventos lunch_out: %s", [dt.strftime('%H:%M') for dt in lunch_out_events])
        logger.debug("Eventos lunch_in: %s", [dt.strftime('%H:%M') for dt in lunch_in_events])
        logger.debug("Eventos in: %s", [dt.strftime('%H:%M') for dt in in_events])
        logger.debug("Eventos out: %s", [dt.strftime('%H:%M') for dt in out_events])

        # --- PASO 2: Entrada y salida principal (FIX) ---
        # Antes: si no había 'in', usábamos la primera marca -> eso entrega 20:02 como entrada.
        # Ahora: si no hay 'in', se queda en None (se completará en el caller con hr.attendance).
        first_in = in_events[0] if in_events else None
        last_out = out_events[-1] if out_events else None

        logger.debug("Entrada detectada: %s", fmt(first_in))
        logger.debug("Salida detectada: %s", fmt(last_out))

        # --- PASO 3: Detección de comida (igual que antes, prioriza checadas reales) ---
        # --- PASO 3: Detección de comida ---
        lunch_out = lunch_in = None
        ls_plan, le_plan = (planned_lunch or (None, None))
        logger.debug("Comida planificada: %s a %s", fmt(ls_plan) if ls_plan else "None", fmt(le_plan) if le_plan else "None")

        # 3.1 Checadas explícitas (ignorando domingo)
        if not is_sunday:
            if lunch_out_events and lunch_in_events:
                lo = min(lunch_out_events)
                li = max(lunch_in_events)
                if li > lo:
                    lunch_out, lunch_in = lo, li
                    logger.debug("Ambos tipos válidos: lunch_out=%s, lunch_in=%s", fmt(lunch_out), fmt(lunch_in))

            elif lunch_out_events and not lunch_in_events:
                # Sólo hay códigos 4 → usar primero/último como ventana de comida
                lo_first = min(lunch_out_events)
                lo_last  = max(lunch_out_events)
                if lo_last > lo_first:
                    dur = lo_last - lo_first
                    if timedelta(minutes=20) <= dur <= timedelta(hours=2):
                        lunch_out, lunch_in = lo_first, lo_last
                        logger.debug("Solo lunch_out: usando primero y último: %s a %s", fmt(lunch_out), fmt(lunch_in))
                # Si aún falta cerrar, asumir +60m (cap a salida si existe)
                if lunch_out is None or lunch_in is None:
                    lunch_out = lunch_out or lo_first
                    li = lunch_out + timedelta(hours=1)
                    if last_out and li > last_out:
                        li = last_out
                    lunch_in = lunch_in or li
                    logger.debug("Solo lunch_out: sin par → asumiendo +60m: %s", fmt(lunch_in))

            elif lunch_in_events and not lunch_out_events:
                # Caso raro: sólo códigos 5 → asumir -60m
                li = max(lunch_in_events)
                lo = li - timedelta(hours=1)
                lunch_out, lunch_in = lo, li
                logger.debug("Solo lunch_in: asumiendo -60m: %s a %s", fmt(lunch_out), fmt(lunch_in))

        # 3.2 Inferir por calendario (usar SOLO checadas de comida)
        if not is_sunday and (lunch_out is None or lunch_in is None) and ls_plan and le_plan:
            TOL = timedelta(minutes=90)
            window_start = ls_plan - TOL
            window_end   = le_plan + TOL
            lunch_times = [dt for dt in (lunch_out_events + lunch_in_events)
                        if window_start <= dt <= window_end]
            if lunch_times:
                lunch_out = lunch_out or min(lunch_times)
                lunch_in  = lunch_in  or max(lunch_times)
                logger.debug("Comida inferida por checadas de comida en ventana: %s a %s", fmt(lunch_out), fmt(lunch_in))
            else:
                lunch_out, lunch_in = ls_plan, le_plan
                logger.debug("Comida por calendario: %s a %s", fmt(lunch_out), fmt(lunch_in))

        # 3.3 Validar duración
        if lunch_out and lunch_in:
            if lunch_in <= lunch_out:
                lunch_in = lunch_out + timedelta(hours=1)
            lunch_duration = lunch_in - lunch_out
            if not (timedelta(minutes=20) <= lunch_duration <= timedelta(hours=2)):
                logger.debug("Duración de comida no válida (%s), descartando/completando por plan)", lunch_duration)
                if ls_plan and le_plan:
                    lunch_out, lunch_in = ls_plan, le_plan
                else:
                    lunch_out = lunch_in = None
            else:
                logger.debug("Duración de comida válida: %s", lunch_duration)

        # 3.4 Domingo: se ignora comida
        if is_sunday:
            logger.debug("Domingo detectado: ignorando checadas y ventana de comida.")
            lunch_out = lunch_in = None
        # --- PASO 4: Horas trabajadas ---
        work_secs = 0
        lunch_secs = 0
        if first_in and last_out and last_out > first_in:
            total_secs = int((last_out - first_in).total_seconds())
            if lunch_out and lunch_in and lunch_in > lunch_out:
                lunch_secs = int((lunch_in - lunch_out).total_seconds())
                work_secs = max(0, total_secs - lunch_secs)
            else:
                work_secs = total_secs

        # --- PASO 5: Retardo ---
        retardo_sec = 0
        if not is_rest and first_in and expected_start and first_in > expected_start:
            retardo_sec = int((first_in - expected_start).total_seconds())
        # <<< NUEVO: contar retardo por minutos completos (ignorar segundos) >>>
        if retardo_sec > 0:
            retardo_sec = (retardo_sec // 60) * 60


        logger.debug("=== RESULTADO FINAL ===")
        logger.debug("Entrada: %s", fmt(first_in))
        logger.debug("Comida inicio: %s", fmt(lunch_out))
        logger.debug("Comida fin: %s", fmt(lunch_in))
        logger.debug("Salida: %s", fmt(last_out))
        logger.debug("Horas trabajo: %s", hhmm(work_secs))
        logger.debug("Horas comida: %s", hhmm(lunch_secs))
        logger.debug("Retardo: %s", hhmm(retardo_sec))
        logger.debug("========================\n")

        return {
            'entrada':    fmt(first_in),
            'comida_ini': fmt(lunch_out),
            'comida_fin': fmt(lunch_in),
            'salida':     fmt(last_out),
            'h_trab':     hhmm(work_secs),
            'h_comida':   hhmm(lunch_secs),
            'h_extra':    '00:00',
            'retardo':    hhmm(retardo_sec),
            'retardo_sec': retardo_sec,
            'has_attendance': bool(first_in or last_out),
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

        # Trae cualquier asistencia que toque el rango:
        # check_in <= fin Y (check_out es nulo O check_out >= inicio)
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
        # Wizard y dataset
        wiz = self.env['attendance.report.wizard'].browse(docids)[:1]
        ds = wiz._fetch_dataset()  # { employees, day_list, per_emp_day, dfrom, dto, tz, include_signature, ... }

        # Empleados del dataset o fallback
        employees = list(ds.get('employees') or self.env['hr.employee'].search([('active', '=', True)]))

        # Lista de días (date) del dataset o fallback
        def _as_date(dt):
            return dt.date() if hasattr(dt, 'date') else dt
        def _iter_days(d1, d2):
            from datetime import timedelta
            cur = d1
            while cur <= d2:
                yield cur
                cur += timedelta(days=1)

        dfrom_d = _as_date(ds['dfrom'])
        dto_d   = _as_date(ds['dto'])
        day_list = list(ds.get('day_list') or _iter_days(dfrom_d, dto_d))

        cards = []
        THRESH_WEEK_SEC = 10 * 60  # 10 minutos acumulables/semana

        for emp in employees:
            filas_tmp = []

            # Índice por día del dataset (si existe)
            per_emp_day_all = ds.get('per_emp_day', {}) or {}
            emp_days = per_emp_day_all.get(emp.id)

            # Fallback: si no hay datos del checador para el empleado, arma desde hr.attendance
            if not emp_days:
                emp_days = self._build_events_index_from_attendance(emp, ds['dfrom'], ds['dto'])

            # Índice de ausencias (vacaciones, permisos, etc.)
            leave_idx = self._build_leave_index(emp, ds['dfrom'], ds['dto'])

            for d in day_list:
                is_rest = self._is_rest_day(emp, d)
                
                # Obtener segmentos del calendario
                segs = self._planned_segments(emp, d)
                
                # ENCONTRAR EL SEGMENTO DE COMIDA (break)
                lunch_seg = None
                for s in segs:
                    if s['kind'] == 'break':
                        lunch_seg = (s['start'], s['end'])
                        break
                
                # Si no hay segmento de break, buscar cualquier intervalo largo (>1h) entre trabajo
                if not lunch_seg and len(segs) >= 2:
                    # Buscar el hueco más grande entre segmentos de trabajo
                    max_gap = timedelta(0)
                    for i in range(len(segs) - 1):
                        if segs[i]['kind'] == 'work' and segs[i + 1]['kind'] == 'work':
                            gap = segs[i + 1]['start'] - segs[i]['end']
                            if gap > max_gap and gap >= timedelta(minutes=30):
                                max_gap = gap
                                lunch_seg = (segs[i]['end'], segs[i + 1]['start'])
                
                # Entrada esperada (primer segmento de trabajo)
                work_segs = [s for s in segs if s['kind'] == 'work']
                expected_start = work_segs[0]['start'] if work_segs else self._expected_start_local(emp, d, is_rest)

                # Construir eventos crudos del día (naive local)
                events_raw = []
                if d in emp_days:
                    for event in emp_days[d]:
                        event_time = event[0]  # datetime (puede venir aware local)
                        event_type = event[1]  # 'in'/'out' (y quizá 'lunch_in'/'lunch_out')

                        # Normaliza a naive (quitando tz si trae)
                        if event_time and hasattr(event_time, 'tzinfo') and event_time.tzinfo:
                            event_time = event_time.replace(tzinfo=None)

                        events_raw.append((event_time, event_type))

                # Procesa IN/OUT + Comida (explícita, inferida o por defecto)
                row = self._process_attendance_data(events_raw, expected_start, is_rest,
                                    planned_lunch=lunch_seg, planned_segments=segs)

                # Asistencia robusta (no usar strings "00:00" como truthy)
                has_attendance = row.pop('has_attendance', None)
                if has_attendance is None:
                    def _nz(x):  # no vacío y distinto de "00:00"
                        return bool(x) and str(x) != '00:00'
                    has_attendance = _nz(row.get('entrada')) or _nz(row.get('salida'))

                # Status base
                if is_rest:
                    status = 'Descanso'
                    row['retardo'] = '00:00'
                    row['retardo_sec'] = 0
                    # --- NUEVO: pintar guiones en descanso ---
                    row.update({
                        'entrada': DASH, 'comida_ini': DASH, 'comida_fin': DASH, 'salida': DASH,
                        'h_trab': DASH, 'h_comida': DASH, 'h_extra': DASH,
                    })
                else:
                    if has_attendance:
                        status = 'Asistencia'
                        # --- marcar retardo por día ---
                        if int(row.get('retardo_sec', 0)) > GRACE_DAILY_SEC:
                            status = 'Retardo'
                    else:
                        status = 'Falta'
                        # --- pintar guiones en faltas ---
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

            # Acumulado semanal de retardos (solo laborables con asistencia)
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

            # Normaliza filas para la salida (limpia llaves internas)
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
                'retardo_total': self._fmt_hhmm_from_seconds(retardo_total_sec) if hasattr(self, '_fmt_hhmm_from_seconds') else (
                    f"{retardo_total_sec//3600:02d}:{(retardo_total_sec%3600)//60:02d}"
                ),
                'rows': filas,
            })

        # Título con fechas en TZ del usuario
        tz = pytz.timezone(ds.get('tz') or 'UTC')

        def _to_local(dt):
            aware = pytz.utc.localize(dt) if getattr(dt, 'tzinfo', None) is None else dt.astimezone(pytz.UTC)
            return aware.astimezone(tz)

        start_local = _to_local(ds['dfrom'])
        end_local   = _to_local(ds['dto'])

        title = f"Registro de asistencia del {_title_spanish(start_local)} al {_title_spanish(end_local)}."
        cpp = 4  # cards per page

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
