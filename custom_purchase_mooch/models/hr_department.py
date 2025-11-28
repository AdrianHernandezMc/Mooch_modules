from odoo import models, fields, api

class Department(models.Model):
    _inherit = 'hr.department'

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Cuenta Analítica',
        help='Cuenta analítica vinculada a este departamento',
    )
    budget_password = fields.Char(
        string='Contraseña de Presupuesto',
        help='Contraseña para acceder al presupuesto de este departamento'
    )

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Sobrescribir para ocultar el campo a usuarios no administradores"""
        fields = super().fields_get(allfields, attributes)
        
        # Si el usuario no es administrador, ocultar budget_password
        if not self.env.user.has_group('base.group_system'):
            if 'budget_password' in fields:
                fields['budget_password']['selectable'] = False
                fields['budget_password']['searchable'] = False
        
        return fields
