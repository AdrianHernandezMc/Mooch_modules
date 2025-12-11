from odoo import models, fields, api

class PosBill(models.Model):
    _inherit = 'pos.bill'

    money_type = fields.Selection([
        ('bill', 'Billete'),
        ('coin', 'Moneda')
    ], string='Tipo', default='bill', required=True)

class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def _loader_params_pos_bill(self):
        result = super()._loader_params_pos_bill()
        result['search_params']['fields'].append('money_type')
        return result