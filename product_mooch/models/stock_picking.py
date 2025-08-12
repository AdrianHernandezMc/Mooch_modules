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

    @api.depends(
        'move_ids_without_package.product_uom_qty',
        'move_ids_without_package.move_line_ids.qty_done'
    )
    def _compute_total_pieces(self):
        uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        for picking in self:
            total = 0.0

            # ¿Ya hay operaciones (no canceladas)? entonces tomamos lo REAL
            has_ops = bool(picking.move_line_ids.filtered(lambda l: l.state != 'cancel'))
            if has_ops:
                for ml in picking.move_line_ids.filtered(lambda l: l.state != 'cancel'):
                    qty = ml.qty_done or 0.0
                    uom = ml.product_uom_id or ml.move_id.product_uom
                    if uom_unit and uom and uom.category_id == uom_unit.category_id:
                        qty = uom._compute_quantity(qty, uom_unit)
                    total += qty
            else:
                # Si no hay operaciones aún, usamos lo ESPERADO de los moves (no cancelados)
                for mv in picking.move_ids.filtered(lambda m: m.state != 'cancel'):
                    qty = mv.product_uom_qty or 0.0
                    uom = mv.product_uom
                    if uom_unit and uom and uom.category_id == uom_unit.category_id:
                        qty = uom._compute_quantity(qty, uom_unit)
                    total += qty

            # Piezas → entero
            picking.total_pieces = int(round(total))