# models/product_selector.py
from odoo import models, fields

class ProductProductSelector(models.TransientModel):
    _name = 'product.product.selector'
    _description = 'Línea del selector'

    wizard_id = fields.Many2one('product.selector.wizard', string='Wizard')
    x_selected = fields.Boolean(string='Seleccionar')
    product_id = fields.Many2one('product.product', string='Producto')
    name = fields.Char(related='product_id.name', string='Nombre', readonly=True)
    default_code = fields.Char(related='product_id.default_code', string='Referencia', readonly=True)
