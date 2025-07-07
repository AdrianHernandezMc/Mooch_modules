from odoo import models, fields

class CrossoveredBudgetLine(models.Model):
    _inherit = 'crossovered.budget.lines'

    department_id = fields.Many2one(
        'hr.department',
        string="Departamento",
    )