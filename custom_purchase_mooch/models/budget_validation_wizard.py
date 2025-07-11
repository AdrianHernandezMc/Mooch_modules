from odoo import models, fields, api

class BudgetValidationWizard(models.TransientModel):
    _name = 'budget.validation.wizard'
    _description = 'Presupuesto Validado'

    message = fields.Html(string="Resultado de Validación")

    def show_budget_results(self):
        return {
            'name': 'Validación de Presupuesto',
            'type': 'ir.actions.act_window',
            'res_model': 'budget.validation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.id,
            'context': self.env.context,
        }
    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}