from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    profit_margin_list = fields.Float(string='Porcentaje de Utilidad Contado', help="Porcentaje de ganancia sobre el costo")
    profit_margin_cred = fields.Float(string='Porcentaje de Utilidad Crédito', help="Porcentaje de ganancia sobre el costo")
    sale_type_basic = fields.Float(string='Tipo de Compra Basico', help="Porcentaje de venta de productos basicos")
    sale_type_trend = fields.Float(string='Tipo de Compra Moda', help="Porcentaje de venta de productos moda")
    sale_type_home = fields.Float(string='Tipo de Compra Hogar', help="Porcentaje de venta de productos hogar")
    sale_type_season = fields.Float(string='Tipo de Compra Temporada', help='Porcentaje de venta de productos temporada')
    sale_type_shoe = fields.Float(string='Tipo de Compra Calzado', help='Porcentaje de venta de productos de calzado')

    @api.model
    def set_values(self):
        """ Guarda los valores de configuración en ir.config_parameter """
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].set_param('product_mooch.profit_margin_list', self.profit_margin_list)
        self.env['ir.config_parameter'].set_param('product_mooch.profit_margin_cred', self.profit_margin_cred)
        self.env['ir.config_parameter'].set_param('product_mooch.sale_type_basic', self.sale_type_basic)
        self.env['ir.config_parameter'].set_param('product_mooch.sale_type_trend',self.sale_type_trend)
        self.env['ir.config_parameter'].set_param('product_mooch.sale_type_home',self.sale_type_home)
        self.env['ir.config_parameter'].set_param('product_mooch.sale_type_season', self.sale_type_season)
        self.env['ir.config_parameter'].set_param('product_mooch.sale_type_shoe', self.sale_type_shoe)

    @api.model
    def get_values(self):
        """ Obtiene los valores de configuración desde ir.config_parameter """
        res = super(ResConfigSettings, self).get_values()
        res.update(
            profit_margin_list=self.env['ir.config_parameter'].sudo().get_param('product_mooch.profit_margin_list', default=0.0),
            profit_margin_cred=self.env['ir.config_parameter'].sudo().get_param('product_mooch.profit_margin_cred', default=0.0),
            sale_type_basic=self.env['ir.config_parameter'].sudo().get_param('product_mooch.sale_type_basic', default=0.0),
            sale_type_trend=self.env['ir.config_parameter'].sudo().get_param('product_mooch.sale_type_trend', default=0.0),
            sale_type_home=self.env['ir.config_parameter'].sudo().get_param('product_mooch.sale_type_home', default=0.0),
            sale_type_season=self.env['ir.config_parameter'].sudo().get_param('product_mooch.sale_type_season', default=0.0),
            sale_type_shoe=self.env['ir.config_parameter'].sudo().get_param('product_mooch.sale_type_shoe', default=0.0)
        )
        return res