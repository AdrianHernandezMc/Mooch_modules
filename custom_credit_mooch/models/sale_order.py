from odoo import models, fields, api
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    credit_limit = fields.Monetary(
        string="Límite Crédito",
        compute='_compute_credit_from_partner',
        readonly=True,
        currency_field='currency_id',
        store=False,
    )
    credit_available = fields.Monetary(
        string="Crédito Disponible",
        compute='_compute_credit_from_partner',
        readonly=True,
        currency_field='currency_id',
        store=False,
    )

    @api.depends('partner_id.credit_limit', 'partner_id.credit_available')
    def _compute_credit_from_partner(self):
        for order in self:
            order.credit_limit = order.partner_id.credit_limit or 0.0
            order.credit_available = order.partner_id.credit_available or 0.0

    def action_confirm(self):
        for order in self:
            if order.credit_available < order.amount_total:
                raise UserError(
                    f"El cliente {order.partner_id.name} excede su límite de crédito.\n"
                    f"Disponible: {order.credit_available} — Pedido: {order.amount_total}"
                )
        return super().action_confirm()
