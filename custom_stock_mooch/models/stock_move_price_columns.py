from odoo import models, fields, api

class StockMove(models.Model):
    _inherit = 'stock.move'

    price_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda (OC)',
        compute='_compute_po_price_vals',
        store=True,
    )
    po_unit_cost = fields.Monetary(
        string='Costo (OC)',
        currency_field='price_currency_id',
        compute='_compute_po_price_vals',
        store=True,
        help='Precio unitario de la línea de compra (con descuento si aplica).'
    )
    po_line_total = fields.Monetary(
        string='Total línea (OC)',
        currency_field='price_currency_id',
        compute='_compute_po_price_vals',
        store=True,
        help='Costo (OC) × Demanda del movimiento, convertido a la UdM de la OC.'
    )

    @api.depends(
        'purchase_line_id.price_unit', 'purchase_line_id.discount',
        'purchase_line_id.currency_id', 'purchase_line_id.product_uom',
        'quantity', 'product_uom', 'state', 'company_id.currency_id'
    )
    def _compute_po_price_vals(self):
        for mv in self:
            pol = mv.purchase_line_id
            if pol:
                currency = pol.currency_id
                # precio unitario efectivo con descuento de la línea (si existe el campo)
                unit_price = pol.price_unit
                if 'discount' in pol._fields:
                    unit_price = unit_price * (1.0 - (pol.discount or 0.0) / 100.0)

                # cantidad de Demanda convertida a la UdM de la OC
                qty = mv.quantity or 0.0
                if mv.product_uom and pol.product_uom and mv.product_uom != pol.product_uom:
                    qty = mv.product_uom._compute_quantity(qty, pol.product_uom, rounding_method='HALF-UP')

                line_total = unit_price * qty

                mv.price_currency_id = currency
                mv.po_unit_cost = currency.round(unit_price) if currency else unit_price
                mv.po_line_total = currency.round(line_total) if currency else line_total
            else:
                # Sin OC: mostramos 0 y fijamos moneda de la compañía (evita errores de Monetary)
                currency = mv.company_id.currency_id
                mv.price_currency_id = currency
                mv.po_unit_cost = 0.0
                mv.po_line_total = 0.0
