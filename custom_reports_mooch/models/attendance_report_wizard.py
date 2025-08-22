# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from datetime import datetime, date, time, timedelta
from collections import defaultdict
import pytz

class AttendanceReportWizard(models.TransientModel):
    _name = "attendance.report.wizard"
    _description = "Asistencias - Reporte PDF (desde daily.attendance)"

    # --- NUEVO: default a 'Tlajomulco'
    @api.model
    def _default_work_location_id(self):
        # Busca por nombre (insensible a mayúsculas) en la compañía del usuario si aplica
        domain = [('name', 'ilike', 'Tlajomulco')]
        # Si tu modelo tiene company_id y quieres acotar:
        if 'company_id' in self.env['hr.work.location']._fields:
            domain = ['|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)] + domain
        loc = self.env['hr.work.location'].search(domain, limit=1)
        return loc.id or False

    date_from = fields.Datetime(required=True, default=lambda s: fields.Datetime.now() - timedelta(days=7))
    date_to   = fields.Datetime(required=True,   default=lambda s: fields.Datetime.now())

    work_location_id = fields.Many2one(
        "hr.work.location",
        string="Sucursal",
        default=_default_work_location_id,   # <<< AQUÍ
        help="Filtra empleados por su ubicación de trabajo."
    )

    employee_ids = fields.Many2many(
        "hr.employee",
        domain="[('active','=',True)] if not work_location_id else [('active','=',True), ('work_location_id','=', work_location_id)]",
        help="Si dejas vacío, se incluirán todos los empleados (o los de la sucursal seleccionada)."
    )

    include_signature = fields.Boolean(default=True)
    cards_per_page = fields.Selection([('2','2 por hoja'), ('3','3 por hoja')], default='2', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Si aún no hay sucursal seteada por contexto u otra lógica, aplica Tlajomulco
        if not res.get('work_location_id'):
            wl = self._default_work_location_id()
            if wl:
                res['work_location_id'] = wl

        # Prefill cuando se llama desde la lista Daily Attendance (tu lógica existente)
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

    @api.onchange('work_location_id')
    def _onchange_work_location_id(self):
        if self.work_location_id and self.employee_ids:
            self.employee_ids = [(6, 0, self.employee_ids.filtered(
                lambda e: e.work_location_id == self.work_location_id
            ).ids)]


    # ----------------- DATASET SOLO DESDE daily.attendance -----------------
    def _fetch_dataset(self):
        """Devuelve estructura para QWeb leyendo únicamente daily.attendance."""
        self.ensure_one()
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        dfrom = fields.Datetime.from_string(self.date_from)
        dto   = fields.Datetime.from_string(self.date_to)
        if dfrom > dto:
            dfrom, dto = dto, dfrom

        # ⬇⬇⬇ AQUÍ se respeta la sucursal si está elegida; si no hay empleados seleccionados,
        # se traen todos los activos (limitados a sucursal si está definida).
        emp_domain = [('active', '=', True)]
        if self.work_location_id:
            emp_domain.append(('work_location_id', '=', self.work_location_id.id))

        employees = self.employee_ids or self.env['hr.employee'].search(emp_domain, order='work_location_id,name')
        emp_ids = set(employees.ids)

        DA = self.env['daily.attendance'].sudo()
        dom = ['|', ('punching_time', '>=', dfrom), ('punching_time', '=', False),
               '|', ('punching_time', '<=', dto),   ('punching_time', '=', False)]
        dom += ['|', ('punching_day', '>=', dfrom.date()), ('punching_day', '=', False),
                '|', ('punching_day', '<=', dto.date()),   ('punching_day', '=', False)]
        if employees:
            dom.append(('employee_id', 'in', list(emp_ids)))

        recs = DA.search(dom, order="employee_id, punching_time, punching_day")

        def _norm_type(v):
            s = (v or '').lower().strip()
            if 'out' in s: return 'out'
            if 'in' in s:  return 'in'
            return 'in'

        logs = []
        for r in recs:
            when = r.punching_time
            if not when and r.punching_day:
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

        day_list = []
        day = dfrom.date()
        while day <= dto.date():
            day_list.append(day)
            day += timedelta(days=1)

        from collections import defaultdict as dd
        per_emp_day = dd(lambda: dd(list))
        for lg in logs:
            loc = pytz.utc.localize(lg['when']).astimezone(tz)
            per_emp_day[lg['employee_id']][loc.date()].append((loc, lg['punch'], lg['addr']))

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
