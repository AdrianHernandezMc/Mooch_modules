# -*- coding: utf-8 -*-
from odoo import models
from datetime import datetime, date, timedelta
from collections import defaultdict

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
    def _process_attendance_data(self, events, expected_start):
        vals = {
            'entrada': '',
            'comida_ini': '',
            'comida_fin': '',
            'salida': '',
            'h_trab': '00:00',
            'h_comida': '00:00',
            'h_extra': '00:00',
            'retardo': '00:00',
            'retardo_sec': 0,
        }
        if not events:
            return vals

        ev = self._normalize_events(events)

        # Entrada = primer IN ; Salida = último OUT (con fallback)
        entrada_dt = next((dt for dt, t in ev if t == 'in'), ev[0][0])
        salida_dt  = next((dt for dt, t in reversed(ev) if t == 'out'), ev[-1][0])

        # Comida = primer OUT + siguiente IN
        comida_ini = None
        comida_fin = None
        for i, (dt, t) in enumerate(ev):
            if t == 'out':
                comida_ini = dt
                for j in range(i + 1, len(ev)):
                    if ev[j][1] == 'in':
                        comida_fin = ev[j][0]
                        break
                break

        # Horas trabajadas sumando tramos in→out
        work_sec, pin = 0, None
        for dt, t in ev:
            if t == 'in' and pin is None:
                pin = dt
            elif t == 'out' and pin is not None:
                work_sec += int((dt - pin).total_seconds())
                pin = None

        # Fallback si no se logró emparejar nada pero hay al menos 2 marcas:
        if work_sec == 0 and entrada_dt and salida_dt and salida_dt > entrada_dt:
            work_sec = int((salida_dt - entrada_dt).total_seconds())
            # Heurística de comida: usar 2ª y 3ª marcas si existen
            if len(ev) >= 3:
                comida_ini = ev[1][0]
                comida_fin = ev[2][0] if len(ev) >= 3 else None

        # Comida válida 30–120 min
        lunch_sec = 0
        if comida_ini and comida_fin:
            lunch_time = int((comida_fin - comida_ini).total_seconds())
            if 1800 <= lunch_time <= 7200:
                lunch_sec = lunch_time

        neto_sec = max(0, work_sec - lunch_sec)
        ot_sec = max(0, neto_sec - 8 * 3600)

        # Retardo contra hora esperada
        delay_sec = 0
        if expected_start and entrada_dt:
            delay_sec = max(0, int((entrada_dt - expected_start).total_seconds()))

        vals.update({
            'entrada': entrada_dt.strftime('%H:%M') if entrada_dt else '',
            'comida_ini': comida_ini.strftime('%H:%M') if comida_ini else '',
            'comida_fin': comida_fin.strftime('%H:%M') if comida_fin else '',
            'salida': salida_dt.strftime('%H:%M') if salida_dt else '',
            'h_trab': _fmt_hhmm_from_seconds(neto_sec),
            'h_comida': _fmt_hhmm_from_seconds(lunch_sec),
            'h_extra': _fmt_hhmm_from_seconds(ot_sec),
            'retardo': _fmt_hhmm_from_seconds(delay_sec),
            'retardo_sec': delay_sec,
        })
        return vals

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

        for att in recs:
            if att.check_in:
                events_by_day[att.check_in.date()].append((att.check_in, 'in'))
            if att.check_out:
                events_by_day[att.check_out.date()].append((att.check_out, 'out'))

        return events_by_day


    # ---------- Armado del reporte ----------
    def _get_report_values(self, docids, data=None):
        wiz = self.env['attendance.report.wizard'].browse(docids)[:1]
        ds = wiz._fetch_dataset()  # { employees, day_list, per_emp_day, dfrom, dto, ... }

        # === NUEVO: empleados por defecto si el wizard no trae ===
        employees = list(ds.get('employees') or self.env['hr.employee'].search([('active', '=', True)]))

        # === NUEVO: day_list por defecto si el dataset no trae ===
        dfrom_d = _as_date(ds['dfrom'])
        dto_d   = _as_date(ds['dto'])
        day_list = list(ds.get('day_list') or _iter_days(dfrom_d, dto_d))

        cards = []
        THRESH_WEEK_SEC = 10 * 60  # 10 minutos acumulables/semana

        for emp in employees:
            filas_tmp = []

            # per_emp_day del dataset (si existe)
            per_emp_day_all = ds.get('per_emp_day', {}) or {}
            emp_days = per_emp_day_all.get(emp.id)

            # === NUEVO: si no hay datos en el dataset, consulta hr.attendance ===
            if not emp_days:
                emp_days = self._build_events_index_from_attendance(emp, ds['dfrom'], ds['dto'])

            # índice de ausencias (vacaciones, permisos, etc.)
            leave_idx = self._build_leave_index(emp, ds['dfrom'], ds['dto'])

            for d in day_list:
                is_rest = self._is_rest_day(emp, d)
                expected_start = self._expected_start_local(emp, d, is_rest)

                events_raw = emp_days.get(d, [])
                row = self._process_attendance_data(events_raw, expected_start)

                has_attendance = bool(row['entrada'] or row['salida'])

                if is_rest:
                    status = 'Descanso'
                    row['retardo'] = '00:00'
                    row['retardo_sec'] = 0
                else:
                    status = 'Falta' if not has_attendance else 'Asistencia'

                # leave del día
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

            # acumulado semanal de retardos
            from collections import defaultdict
            sum_week = defaultdict(int)
            for r in filas_tmp:
                if not r['is_rest'] and r['has_attendance']:
                    sum_week[r['week_key']] += r.get('retardo_sec', 0)

            # total de retardo del periodo (solo días laborables con asistencia)
            retardo_total_sec = sum(
                r.get('retardo_sec', 0)
                for r in filas_tmp
                if not r['is_rest'] and r['has_attendance']
            )

            filas = []
            for r in filas_tmp:
                if r['status'] == 'Asistencia' and r.get('retardo_sec', 0) > 0:
                    if sum_week[r['week_key']] > THRESH_WEEK_SEC:
                        r['status'] = 'Retardo'
                # limpiar llaves internas
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
