from odoo import models, fields, api
from odoo.addons.decimal_precision import dp

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    invoice_tag_ids = fields.Many2many(
        'purchase.invoice.tag',
        'purchase_order_invoice_tag_rel',
        'order_id',
        'tag_id',
        string="Facturas Proveedor",
        help="Añade aquí tantas referencias de factura como necesites",
    )

    discount_global = fields.Float(
        string="Descuento Global (%)",
        default=0.0,
        digits=dp.get_precision('Discount'),
        help="Porcentaje que se aplicará a todas las líneas",
    )

    total_discount = fields.Monetary(
        string="Total Descuento",
        compute="_compute_total_discount",
        store=True,
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Departamento',
        help='Departamento responsable de este pedido',
    )

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string="Cuenta Analítica",
        help="Cuenta analítica sobre la que se controlará el presupuesto",
    )

    @api.depends('order_line.price_unit', 'order_line.product_qty', 'order_line.discount')
    def _compute_total_discount(self):
        for order in self:
            total = sum(
                line.price_unit * line.product_qty * line.discount / 100.0
                for line in order.order_line
            )
            order.total_discount = total

    @api.onchange('discount_global')
    def _onchange_discount_global(self):
        # Actualiza cada línea de inmediato en el formulario
        for line in self.order_line:
            line.discount = self.discount_global or 0.0

    def action_open_product_selector(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Selector de Productos',
            'res_model': 'product.selector.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_id': self.id,
            },
        }

    @api.onchange('product_id')
    def _onchange_product_analytic_account(self):
        # Si aún no hay nada en el pedido, proponemos la cuenta del producto
        if self.product_id and not self.order_id.analytic_account_id:
            self.order_id.analytic_account_id = (
                self.product_id.analytic_account_id
                or self.product_id.categ_id.computed_analytic_account_id
            )