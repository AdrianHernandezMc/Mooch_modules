from odoo import models, fields, api
from odoo.addons.decimal_precision import dp

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    discount_global = fields.Float(
        string="Descuento Original (%)",
        help="Porcentaje de descuento antes de aplicar el Descuento Global",
        digits=dp.get_precision('Discount'),
    )

    discount = fields.Float(
        string='Disc. (%)',
        compute='_compute_global_discount',
        inverse='_inverse_global_discount',
        store=True,
        digits=dp.get_precision('Discount'),
    )

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string="Cuenta Analítica",
        help="Primera línea de la distribución analítica.",
        compute='_compute_analytic_account_id',
        inverse='_inverse_analytic_account_id',
        store=True,
    )

    @api.depends('order_id.discount_global')
    def _compute_global_discount(self):
        for line in self:
            line.discount = line.order_id.discount_global or 0.0

    def _inverse_global_discount(self):
        for line in self:
            line.order_id.discount_global = line.discount

    @api.onchange('discount')
    def _onchange_discount(self):
        """Actualiza discount_global cuando cambia discount"""
        for line in self:
            line.discount_global = line.discount

    @api.depends('analytic_distribution')
    def _compute_analytic_account_id(self):
        for line in self:
            dist = line.analytic_distribution or []
            if isinstance(dist, str):
                try:
                    dist = json.loads(dist)
                except Exception:
                    dist = []
            if dist and isinstance(dist, list) and dist[0].get('account_id'):
                line.analytic_account_id = dist[0]['account_id']
            else:
                line.analytic_account_id = line.order_id.analytic_account_id.id if line.order_id.analytic_account_id else False

    def _inverse_analytic_account_id(self):
        for line in self:
            acct = line.analytic_account_id
            if acct:
                line.analytic_distribution = [{
                    'account_id': acct.id,
                    'percent': 100.0,
                }]
            else:
                line.analytic_distribution = []

    @api.onchange('product_id')
    def _onchange_fill_analytic_from_product(self):
        for line in self:
            if line.product_id and not line.analytic_distribution:
                acct = (
                    line.order_id.analytic_account_id
                    or getattr(line.product_id, 'analytic_account_id', False)
                    or getattr(line.product_id.categ_id, 'computed_analytic_account_id', False)
                )
                if acct:
                    line.analytic_account_id = acct.id

    @api.onchange('product_id')
    def _onchange_product_set_analytic(self):
        for line in self:
            acct = (line.product_id.analytic_account_id
                    or line.product_id.categ_id.computed_analytic_account_id
                    or False)
            if acct:
                line.analytic_distribution = {acct.id: 100.0}