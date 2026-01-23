from odoo import models, fields, api

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    # Campo Almacén
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacén',
        related='location_id.warehouse_id',
        store=True, 
        readonly=True
    )

    # Campo Valor Monetario
    money_value = fields.Monetary(
        string='Valor Inventario',
        compute='_compute_money_value',
        currency_field='company_currency_id',
        store=True 
    )

    company_currency_id = fields.Many2one(
        'res.currency', 
        related='company_id.currency_id', 
        readonly=True
    )

    @api.depends('quantity', 'product_id.standard_price')
    def _compute_money_value(self):
        for record in self:
            # Calculamos: Cantidad a Mano * Costo Estándar
            record.money_value = record.quantity * record.product_id.standard_price