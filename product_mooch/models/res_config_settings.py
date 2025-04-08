from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    profit_margin_list = fields.Float(string='Porcentaje de Utilidad Contado', help="Porcentaje de ganancia sobre el costo")
    profit_margin_cred = fields.Float(string='Porcentaje de Utilidad Crédito', help="Porcentaje de ganancia sobre el costo")

    @api.model
    def set_values(self):
        """ Guarda los valores de configuración en ir.config_parameter """
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].set_param('product_mooch.profit_margin_list', self.profit_margin_list)
        self.env['ir.config_parameter'].set_param('product_mooch.profit_margin_cred', self.profit_margin_cred)

    @api.model
    def get_values(self):
        """ Obtiene los valores de configuración desde ir.config_parameter """
        res = super(ResConfigSettings, self).get_values()
        res.update(
            profit_margin_list=self.env['ir.config_parameter'].sudo().get_param('product_mooch.profit_margin_list', default=0.0),
            profit_margin_cred=self.env['ir.config_parameter'].sudo().get_param('product_mooch.profit_margin_cred', default=0.0),
        )
        return res