# -*- coding: utf-8 -*-
from odoo import models
from datetime import datetime, date, timedelta
from collections import defaultdict
import pytz

# ======= Constantes de formato =======
SPANISH_WEEKDAYS = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
SPANISH_MONTHS = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

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

    # ---------- Cálculo por día ----------
    def _process_attendance_data(self, events_raw, expected_start, is_rest):
        """
        events_raw: lista [(dt_naive, punch)] con punch en {'in','out'} (y si existiera 'lunch_in','lunch_out')
        expected_start: datetime local (naive) con la hora esperada de entrada
        is_rest: bool, si el día es descanso
        """
        from datetime import timedelta

        # === Parámetros ajustables ===
        LUNCH_MIN = timedelta(minutes=30)               # mínimo para considerar un hueco como comida
        LUNCH_MAX = timedelta(hours=3)                  # máximo razonable para una comida
        DEFAULT_LUNCH = timedelta(minutes=60)           # comida por defecto si no hay hueco
        DEFAULT_LUNCH_MIN_SHIFT = timedelta(hours=6)    # turno mínimo para aplicar comida por defecto

        def hhmm(total_secs):
            total_secs = max(0, int(total_secs or 0))
            h = total_secs // 3600
            m = (total_secs % 3600) // 60
            return f"{h:02d}:{m:02d}"

        # Normaliza y ordena (si no trae punch, toma 'in' por defecto)
        logs = [(dt, (p or 'in')) for (dt, p) in events_raw if dt]
        logs.sort(key=lambda x: x[0])

        first_in = next((dt for dt, p in logs if p in ('in', 'lunch_in')), None)
        last_out = next((dt for dt, p in reversed(logs) if p in ('out', 'lunch_out')), None)

        # Comida explícita (por si alguna vez llega como lunch_out/lunch_in)
        lunch_out = next((dt for dt, p in logs if p == 'lunch_out'), None)
        lunch_in  = next((dt for dt, p in logs if p == 'lunch_in' and (not lunch_out or dt >= lunch_out)), None)
        lunch_explicit = bool(lunch_out and lunch_in and lunch_in > lunch_out)

        # Trabajo por tramos (corta en out o lunch_out; reabre en in o lunch_in)
        work_secs = 0
        open_in = None
        for dt, p in logs:
            if p in ('in', 'lunch_in') and open_in is None:
                open_in = dt
            elif p in ('out', 'lunch_out') and open_in:
                work_secs += int((dt - open_in).total_seconds())
                open_in = None
        if open_in and last_out and last_out > open_in:
            work_secs += int((last_out - open_in).total_seconds())

        # === Determinar comida: explícita → inferida por hueco → por defecto centrada en el turno ===
        lunch_secs = 0

        # 1) Hueco real entre first_in y last_out
        if not lunch_explicit and first_in and last_out and last_out > first_in:
            times = [dt for dt, _ in logs if first_in <= dt <= last_out]
            if first_in not in times:
                times.insert(0, first_in)
            if last_out not in times:
                times.append(last_out)

            max_gap = timedelta(0); s = e = None
            for a, b in zip(times, times[1:]):
                gap = b - a
                if gap > max_gap:
                    max_gap = gap; s = a; e = b

            if s and e and LUNCH_MIN <= max_gap <= LUNCH_MAX:
                lunch_out, lunch_in = s, e
                lunch_secs = int((e - s).total_seconds())
                # Ese hueco ya estaba incluido como trabajo; descuéntalo
                work_secs = max(0, work_secs - lunch_secs)

        # 2) Si no hubo hueco válido, aplicar comida por defecto centrada en el turno
        if lunch_secs == 0 and first_in and last_out and last_out > first_in:
            shift = last_out - first_in
            if shift >= DEFAULT_LUNCH_MIN_SHIFT:
                mid = first_in + shift / 2
                lo  = mid - DEFAULT_LUNCH / 2
                li  = mid + DEFAULT_LUNCH / 2
                # Asegura que no salga del turno
                if lo < first_in: lo = first_in
                if li > last_out: li = last_out
                lunch_out, lunch_in = lo, li
                lunch_secs = int((li - lo).total_seconds())
                work_secs = max(0, work_secs - lunch_secs)

        # Retardo vs hora esperada
        retardo_sec = 0
        if not is_rest and first_in and expected_start and first_in > expected_start:
            retardo_sec = int((first_in - expected_start).total_seconds())

        fmt = lambda dt: dt and dt.strftime('%H:%M') or '00:00'
        return {
            'entrada': fmt(first_in),
            'comida_ini': fmt(lunch_out),
            'comida_fin': fmt(lunch_in),
            'salida': fmt(last_out),
            'h_trab': hhmm(work_secs),
            'h_comida': hhmm(lunch_secs),
            'h_extra': '00:00',
            'retardo': hhmm(retardo_sec),
            'retardo_sec': retardo_sec,
            # Flag robusto para decidir Asistencia/Falta
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
                expected_start = self._expected_start_local(emp, d, is_rest)

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
                row = self._process_attendance_data(events_raw, expected_start, is_rest)

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
                else:
                    status = 'Asistencia' if has_attendance else 'Falta'

                # Si hay leave ese día, predomina
                leave = leave_idx.get(_as_date(d))
                if leave:
                    status = leave.holiday_status_id.name or 'Tiempo libre'
                    row.update({
                        'entrada': '', 'comida_ini': '', 'comida_fin': '', 'salida': '',
                        'h_trab': '00:00', 'h_comida': '00:00', 'h_extra': '00:00',
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
