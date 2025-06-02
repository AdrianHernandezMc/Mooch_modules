from odoo import models, fields, api
from odoo.addons.decimal_precision import dp

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # Campo original que guardaba el discount previo
    discount_original = fields.Float(
        string="Descuento Original (%)",
        help="Porcentaje de descuento antes de aplicar el Descuento Global",
        digits=dp.get_precision('Discount'),
    )

    # Redefinimos discount como computado/inverse/store
    discount = fields.Float(
        string='Disc. (%)',
        compute='_compute_global_discount',
        inverse='_inverse_global_discount',
        store=True,
        digits=dp.get_precision('Discount'),
    )

    @api.depends('order_id.discount_global')
    def _compute_global_discount(self):
        for line in self:
            line.discount = line.order_id.discount_global or 0.0

    def _inverse_global_discount(self):
        # Si el usuario edita discount en la línea, actualiza la cabecera
        for line in self:
            line.order_id.discount_global = line.discount

    @api.onchange('discount')
    def _onchange_discount_original(self):
        # Guardamos el valor de discount para histórico
        for rec in self:
            rec.discount_original = rec.discount
