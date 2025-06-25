from odoo import models, api, fields
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    total_pieces = fields.Float(
        string="Total de Piezas",
        compute='_compute_total_pieces',
        readonly=True,
        store=True,
    )

    def action_print_labels(self):
        self.ensure_one()
        product_templates = []
        for line in self.move_line_ids:
            product = line.product_id.product_tmpl_id
            qty = int(line.qty_done or 0)
            if product.active and qty > 0:
                product_templates += [product.id] * qty

        if not product_templates:
            raise UserError("No hay productos activos con cantidad válida en las líneas del traslado.")

        return self.env.ref('product_mooch.action_report_product_labels_from_picking').report_action(product_templates)

    @api.depends('move_line_ids.qty_done')
    def _compute_total_pieces(self):
        for pick in self:
            pick.total_pieces = sum(pick.move_line_ids.mapped('qty_done'))