from odoo import models, fields

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