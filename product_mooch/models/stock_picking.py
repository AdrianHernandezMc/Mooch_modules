from odoo import models, api, fields, _
from odoo.exceptions import UserError
class StockMove(models.Model):
    _inherit = 'stock.move'

    label_selected = fields.Boolean(
        string="Sel. etiqueta",
        help="Marca esta línea para imprimir etiqueta."
    )
class StockPicking(models.Model):
    _inherit = 'stock.picking'

    total_pieces = fields.Float(
        string="Total de Piezas",
        compute='_compute_total_pieces',
        readonly=True,
        store=True,
    )

    def _labels_qty_for_move(self, move):
        """
        Orden de preferencia:
        1) move.quantity (la que ves/edites en Operaciones)
        2) sum(move.move_line_ids.qty_done) (operaciones detalladas)
        3) move.product_uom_qty (demanda)
        """
        qty = int(getattr(move, 'quantity', 0) or 0)
        if qty <= 0 and move.move_line_ids:
            qty = int(sum(move.move_line_ids.mapped('qty_done')))
        if qty <= 0:
            qty = int(move.product_uom_qty or 0)
        return max(qty, 0)

    def action_print_labels(self):
        """
        - Con selección (label_selected): solo esas líneas, N etiquetas por cantidad.
        - Sin selección: como antes, usa qty_done de move_line_ids para repetir; si 0, cae a cantidades del move.
        """
        self.ensure_one()
        moves_all = self.move_ids_without_package or self.move_ids
        selected = moves_all.filtered('label_selected')

        docids = []  # lista de IDs de product.template REPETIDOS

        if selected:
            # Solo seleccionados (Operaciones)
            for mv in selected:
                tmpl = mv.product_id.product_tmpl_id
                n = self._labels_qty_for_move(mv)
                if tmpl and n > 0:
                    docids += [tmpl.id] * n
        else:
            # Comportamiento anterior: primero qty_done de las líneas detalladas
            for ml in self.move_line_ids:
                tmpl = ml.product_id.product_tmpl_id
                n = int(ml.qty_done or 0)
                if tmpl and n > 0:
                    docids += [tmpl.id] * n

            # Si no hay qty_done aún, usar cantidades del move
            if not docids:
                for mv in moves_all:
                    tmpl = mv.product_id.product_tmpl_id
                    n = self._labels_qty_for_move(mv)
                    if tmpl and n > 0:
                        docids += [tmpl.id] * n

        if not docids:
            raise UserError(_("No hay cantidades para imprimir etiquetas."))

        # IMPORTANTE: pasamos la lista con duplicados (NO browse) para que el reporte repita N veces.
        # Usa el XMLID de tu reporte "desde picking". Si el tuyo es distinto, cámbialo aquí.
        return self.env.ref('product_mooch.action_report_product_labels_from_picking').report_action(docids)

    @api.depends(
        'move_ids',                     # altas/bajas de líneas (OC)
        'move_ids.quantity',     # cantidad
        'move_ids.product_uom',         # conversión
        'move_ids.state',
        'state',
    )
    def _compute_total_pieces(self):
        uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        for picking in self:
            total = 0.0
            for mv in picking.move_ids.filtered(lambda m: m.state != 'cancel'):
                # solo contamos si la UoM está en la categoría Unit(s)
                uom = mv.product_uom
                if uom_unit and uom and uom.category_id == uom_unit.category_id:
                    qty = uom._compute_quantity(mv.quantity or 0.0, uom_unit)
                    total += qty
            picking.total_pieces = int(round(total))