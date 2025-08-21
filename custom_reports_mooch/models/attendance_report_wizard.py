# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from datetime import datetime, date, time, timedelta
from collections import defaultdict
import pytz

class AttendanceReportWizard(models.TransientModel):
    _name = "attendance.report.wizard"
    _description = "Asistencias - Reporte PDF (desde daily.attendance)"

    date_from = fields.Datetime(required=True, default=lambda s: fields.Datetime.now() - timedelta(days=7))
    date_to   = fields.Datetime(required=True, default=lambda s: fields.Datetime.now())
    employee_ids = fields.Many2many("hr.employee", domain=[('active','=',True)])
    include_signature = fields.Boolean(default=True)
    cards_per_page = fields.Selection([('2','2 por hoja'), ('3','3 por hoja')], default='2', required=True)

    # Prefill cuando se llama desde la lista Daily Attendance
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
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

    # ----------------- DATASET SOLO DESDE daily.attendance -----------------
    def _fetch_dataset(self):
        """Devuelve estructura para QWeb leyendo únicamente daily.attendance."""
        self.ensure_one()
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        dfrom = fields.Datetime.from_string(self.date_from)
        dto   = fields.Datetime.from_string(self.date_to)
        if dfrom > dto:
            dfrom, dto = dto, dfrom

        employees = self.employee_ids or self.env['hr.employee'].search([('active', '=', True)])
        emp_ids = set(employees.ids)

        DA = self.env['daily.attendance'].sudo()
        # Filtra por punching_time si existe; si no, por punching_day
        dom = ['|', ('punching_time', '>=', dfrom), ('punching_time', '=', False),
               '|', ('punching_time', '<=', dto), ('punching_time', '=', False)]
        # también acota por día (por si hay registros sin datetime)
        dom += ['|', ('punching_day', '>=', dfrom.date()), ('punching_day', '=', False),
                '|', ('punching_day', '<=', dto.date()), ('punching_day', '=', False)]
        if employees:
            dom.append(('employee_id', 'in', list(emp_ids)))

        recs = DA.search(dom, order="employee_id, punching_time, punching_day")

        # Normaliza tipo de marca
        def _norm_type(v):
            s = (v or '').lower().strip()
            if 'out' in s: return 'out'
            if 'in' in s:  return 'in'
            return 'in'

        # Genera lista de logs con datetime en TZ del usuario
        logs = []
        for r in recs:
            when = r.punching_time
            if not when and r.punching_day:
                # si solo hay fecha, toma el inicio del día
                when = pytz.utc.localize(datetime.combine(r.punching_day, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
            if not when:
                continue
            punch = _norm_type(getattr(r, 'punch_type', False) or getattr(r, 'attendance_type', False))
            addr = r.address_id.name if getattr(r, 'address_id', False) else ''
            logs.append({
                'employee_id': r.employee_id.id if r.employee_id else False,
                'when': when,      # naive UTC
                'punch': punch,    # 'in' | 'out'
                'addr': addr,
            })
        logs = [l for l in logs if l['employee_id'] in emp_ids]
        logs.sort(key=lambda l: (l['employee_id'], l['when']))

        # Construir días en rango
        day_list = []
        day = dfrom.date()
        while day <= dto.date():
            day_list.append(day)
            day += timedelta(days=1)

        # Index por empleado/día en la TZ del usuario
        per_emp_day = defaultdict(lambda: defaultdict(list))
        for lg in logs:
            loc = pytz.utc.localize(lg['when']).astimezone(tz)
            per_emp_day[lg['employee_id']][loc.date()].append((loc, lg['punch'], lg['addr']))

        # Máximo de pares por día (E1/S1, E2/S2…)
        max_pairs = {}
        for d in day_list:
            m = 1
            for emp in employees:
                lst = per_emp_day[emp.id].get(d, [])
                ins  = sum(1 for _, p, _ in lst if p == 'in')
                outs = sum(1 for _, p, _ in lst if p == 'out')
                m = max(m, max(ins, outs))
            max_pairs[d] = m

        return {
            'employees': employees,
            'day_list': day_list,
            'per_emp_day': per_emp_day,
            'max_pairs': max_pairs,
            'dfrom': dfrom,
            'dto': dto,
            'tz': self.env.user.tz or 'UTC',
            'include_signature': self.include_signature,
        }
