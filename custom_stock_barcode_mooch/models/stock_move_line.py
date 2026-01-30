from odoo import models, fields

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    quant_rack_area = fields.Char(string="Rack / Área")