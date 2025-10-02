from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    # campo solo para layout
    dummy_break = fields.Boolean(
        string='',
        readonly=True,
        help="Campo vacío para controlar saltos de línea en la vista"
    )
    # — Para Ropa —
    sale_type_clothes_cash   = fields.Float(string='Moda (Contado %)', help="Porcentaje contado para productos de moda")
    sale_type_clothes_credit = fields.Float(string='Moda (Crédito %)', help="Porcentaje crédito para productos de moda")
    # — Para Hogar —
    sale_type_home_cash      = fields.Float(string='Hogar (Contado %)',  help="Porcentaje contado para productos de hogar")
    sale_type_home_credit    = fields.Float(string='Hogar (Crédito %)',  help="Porcentaje crédito para productos de hogar")
    # — Para Calzado —
    sale_type_shoe_cash      = fields.Float(string='Calzado (Contado %)', help="Porcentaje contado para productos de calzado")
    sale_type_shoe_credit    = fields.Float(string='Calzado (Crédito %)', help="Porcentaje crédito para productos de calzado")
    # — Para Ropa de Invierno —
    sale_type_season_cash    = fields.Float(string='Ropa de Invierno (Contado %)', help="Porcentaje contado para productos de temporada")
    sale_type_season_credit  = fields.Float(string='Ropa de Invierno (Crédito %)', help="Porcentaje crédito para productos de temporada")
    # — Para Ropa y articulos 2024 —
    sale_type_old_2024_cash    = fields.Float(string='Productos del 2024 (Contado %)', help="Porcentaje contado para productos del 2024")
    sale_type_old_2024_credit  = fields.Float(string='Productos del 2024 (Crédito %)', help="Porcentaje crédito para productos del 2024")

    @api.model
    def set_values(self):
        super().set_values()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('product_mooch.sale_type_clothes_cash',   self.sale_type_clothes_cash)
        params.set_param('product_mooch.sale_type_clothes_credit', self.sale_type_clothes_credit)
        params.set_param('product_mooch.sale_type_home_cash',      self.sale_type_home_cash)
        params.set_param('product_mooch.sale_type_home_credit',    self.sale_type_home_credit)
        params.set_param('product_mooch.sale_type_shoe_cash',      self.sale_type_shoe_cash)
        params.set_param('product_mooch.sale_type_shoe_credit',    self.sale_type_shoe_credit)
        params.set_param('product_mooch.sale_type_season_cash',    self.sale_type_season_cash)
        params.set_param('product_mooch.sale_type_season_credit',  self.sale_type_season_credit)
        params.set_param('product_mooch.sale_type_old_2024_cash',    self.sale_type_old_2024_cash)
        params.set_param('product_mooch.sale_type_old_2024_credit',  self.sale_type_old_2024_credit)
        # dispara tu cron para que recalcule precios en los productos afectados
        self.env['product.template'].cron_recompute_product_prices()

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update({
            'sale_type_clothes_cash':   float(params.get_param('product_mooch.sale_type_clothes_cash',   default=0.0)),
            'sale_type_clothes_credit': float(params.get_param('product_mooch.sale_type_clothes_credit', default=0.0)),
            'sale_type_home_cash':      float(params.get_param('product_mooch.sale_type_home_cash',      default=0.0)),
            'sale_type_home_credit':    float(params.get_param('product_mooch.sale_type_home_credit',    default=0.0)),
            'sale_type_shoe_cash':      float(params.get_param('product_mooch.sale_type_shoe_cash',      default=0.0)),
            'sale_type_shoe_credit':    float(params.get_param('product_mooch.sale_type_shoe_credit',    default=0.0)),
            'sale_type_season_cash':    float(params.get_param('product_mooch.sale_type_season_cash',    default=0.0)),
            'sale_type_season_credit':  float(params.get_param('product_mooch.sale_type_season_credit',  default=0.0)),
            'sale_type_old_2024_cash':    float(params.get_param('product_mooch.sale_type_old_2024_cash',    default=0.0)),
            'sale_type_old_2024_credit':  float(params.get_param('product_mooch.sale_type_old_2024_credit',  default=0.0)),
        })
        return res