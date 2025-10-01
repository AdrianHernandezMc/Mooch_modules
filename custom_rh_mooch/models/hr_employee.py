import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    fixed_name = fields.Char(
        string="Nombre fijo",
        help=(
            "Nombre canónico del empleado. "
            "Se usará para actualizar automáticamente el nombre principal "
            "cuando otros procesos (p. ej., el checador) lo cambien."
        ),
        groups="hr.group_hr_user",
        tracking=True,
    )

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

    is_administrative = fields.Boolean(
        string="¿Es Administrativo?",
        groups="hr.group_hr_user",
        help="Si está activo, este empleado será considerado en el reporte especial de tiempos administrativos (entrada/comida/regreso/salida)."
    )

    # Poblado inicial: si no se indicó, copiar el nombre actual
    @api.model
    def create(self, vals):
        if not vals.get("fixed_name") and vals.get("name"):
            vals["fixed_name"] = vals["name"]
        return super().create(vals)

    def _is_privileged_to_edit_fixed_name(self):
        """RH Manager o System Admin pueden modificar el nombre fijo sin restricción."""
        return self.user_has_groups("hr.group_hr_manager") or self.user_has_groups("base.group_system")

    def write(self, vals):
        # --- 1) Regla de edición de fixed_name ---
        if "fixed_name" in vals and not self.env.context.get("allow_fixed_name_update"):
            if not self._is_privileged_to_edit_fixed_name():
                for rec in self:
                    if rec.fixed_name and vals.get("fixed_name") and vals["fixed_name"] != rec.fixed_name:
                        raise ValidationError(_(
                            "El 'Nombre fijo' solo se debe capturar una vez.\n"
                            "Si necesitas corregirlo, solicita a RH o a un Administrador "
                            "o usa el contexto 'allow_fixed_name_update'."
                        ))

        # Guardamos primero los cambios solicitados
        res = super().write(vals)

        # --- 2) Si un RH Manager o System Admin cambia 'name', sincronizamos 'fixed_name' ---
        # (para que el cron no lo revierta)
        if "name" in vals and self._is_privileged_to_edit_fixed_name():
            # Si en el mismo write NO vino fixed_name explícito, lo igualamos al nuevo name.
            if "fixed_name" not in vals:
                for rec in self:
                    if rec.name and rec.fixed_name != rec.name:
                        # Evitar la validación del one-time rule
                        rec.with_context(allow_fixed_name_update=True).write({"fixed_name": rec.name})
                        _logger.info(
                            "HR Name Sync immediate: fixed_name actualizado por privilegio (emp_id=%s).", rec.id
                        )

        return res

    # Cron: name <- fixed_name (para revertir cambios del checador)
    @api.model
    def _cron_sync_fixed_employee_names(self, batch_size=500):
        employees = self.search([("fixed_name", "!=", False)], limit=batch_size)
        changed = 0
        for emp in employees:
            if emp.fixed_name and emp.name != emp.fixed_name:
                emp.with_context(allow_fixed_name_update=True).write({"name": emp.fixed_name})
                changed += 1
        if changed:
            _logger.info("HR Name Sync: %s empleados sincronizados (name <- fixed_name).", changed)
        return True