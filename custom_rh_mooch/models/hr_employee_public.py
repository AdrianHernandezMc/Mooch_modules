from odoo import models, fields


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    work_calendar_id = fields.Many2one(
        "resource.calendar",
        string="Horario de trabajo",
        compute="_compute_hr_extra_public",
        compute_sudo=True,
        readonly=True,
        store=False,
    )

    rest_monday = fields.Boolean(compute="_compute_hr_extra_public", compute_sudo=True, readonly=True, store=False)
    rest_tuesday = fields.Boolean(compute="_compute_hr_extra_public", compute_sudo=True, readonly=True, store=False)
    rest_wednesday = fields.Boolean(compute="_compute_hr_extra_public", compute_sudo=True, readonly=True, store=False)
    rest_thursday = fields.Boolean(compute="_compute_hr_extra_public", compute_sudo=True, readonly=True, store=False)
    rest_friday = fields.Boolean(compute="_compute_hr_extra_public", compute_sudo=True, readonly=True, store=False)
    rest_saturday = fields.Boolean(compute="_compute_hr_extra_public", compute_sudo=True, readonly=True, store=False)
    rest_sunday = fields.Boolean(compute="_compute_hr_extra_public", compute_sudo=True, readonly=True, store=False)

    rest_notes = fields.Char(string="Notas de descanso", compute="_compute_hr_extra_public",
                             compute_sudo=True, readonly=True, store=False)

    device_id_num = fields.Char(string="ID Dispositivo (Núm.)", compute="_compute_hr_extra_public",
                                compute_sudo=True, readonly=True, store=False)
    device_id = fields.Many2one("hr.biometric.device", string="Dispositivo Biométrico",
                                compute="_compute_hr_extra_public", compute_sudo=True,
                                readonly=True, store=False)

    def _compute_hr_extra_public(self):
        Employee = self.env["hr.employee"].sudo()
        for rec in self:
            emp = Employee.browse(rec.id)
            if not emp.exists():
                rec.work_calendar_id = False
                rec.rest_monday = False
                rec.rest_tuesday = False
                rec.rest_wednesday = False
                rec.rest_thursday = False
                rec.rest_friday = False
                rec.rest_saturday = False
                rec.rest_sunday = False
                rec.rest_notes = False
                rec.device_id_num = False
                rec.device_id = False
                continue

            rec.work_calendar_id = emp.resource_id.calendar_id.id
            rec.rest_monday = bool(emp.rest_monday)
            rec.rest_tuesday = bool(emp.rest_tuesday)
            rec.rest_wednesday = bool(emp.rest_wednesday)
            rec.rest_thursday = bool(emp.rest_thursday)
            rec.rest_friday = bool(emp.rest_friday)
            rec.rest_saturday = bool(emp.rest_saturday)
            rec.rest_sunday = bool(emp.rest_sunday)
            rec.rest_notes = emp.rest_notes or False
            rec.device_id_num = getattr(emp, "device_id_num", False)
            rec.device_id = getattr(emp, "device_id", False) and emp.device_id.id or False
