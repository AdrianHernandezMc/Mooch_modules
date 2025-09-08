# custom_rh_mooch/models/hr_employee.py
# -*- coding: utf-8 -*-
import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    work_calendar_id = fields.Many2one(
        "resource.calendar",
        string="Horario de trabajo",
        related="resource_id.calendar_id",
        store=True,
        readonly=False,
        groups="hr.group_hr_user",
        help=(
            "Calendario de trabajo (Working Hours) del recurso asociado. "
            "Afecta asistencia, planificación y ausencias."
        ),
    )

    rest_monday = fields.Boolean(string="Lunes", tracking=True, groups="hr.group_hr_user",
                                 help="Descanso semanal el día Lunes.")
    rest_tuesday = fields.Boolean(string="Martes", tracking=True, groups="hr.group_hr_user",
                                  help="Descanso semanal el día Martes.")
    rest_wednesday = fields.Boolean(string="Miércoles", tracking=True, groups="hr.group_hr_user",
                                    help="Descanso semanal el día Miércoles.")
    rest_thursday = fields.Boolean(string="Jueves", tracking=True, groups="hr.group_hr_user",
                                   help="Descanso semanal el día Jueves.")
    rest_friday = fields.Boolean(string="Viernes", tracking=True, groups="hr.group_hr_user",
                                 help="Descanso semanal el día Viernes.")
    rest_saturday = fields.Boolean(string="Sábado", tracking=True, groups="hr.group_hr_user",
                                   help="Descanso semanal el día Sábado.")
    rest_sunday = fields.Boolean(string="Domingo", tracking=True, groups="hr.group_hr_user",
                                 help="Descanso semanal el día Domingo.")

    rest_notes = fields.Char(
        string="Notas de descanso",
        groups="hr.group_hr_user",
        help="Notas u observaciones sobre los días de descanso del empleado."
    )
