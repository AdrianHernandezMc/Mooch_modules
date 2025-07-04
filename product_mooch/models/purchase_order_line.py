from odoo import api, fields, models

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    cost_base = fields.Monetary(
        string='Costo Base',
        currency_field='currency_id',
        store=True,
    )


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_confirm(self):
        res = super().button_confirm()
        for order in self:
            for line in order.order_line:
                if line.cost_base and line.product_id:
                    line.product_id.sudo().write({'cost_base': line.cost_base})
        return res