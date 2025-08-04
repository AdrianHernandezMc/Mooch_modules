import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.models import Command

_logger = logging.getLogger(__name__)

class StockReturnPickingLine(models.TransientModel):
    _inherit = 'stock.return.picking.line'

    # Casilla para seleccionar qué líneas devolver
    to_refund = fields.Boolean(string="Seleccionar", default=False)

class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        lines = []
        # Helper to compute remaining qty on move
        def _remaining_qty(move):
            done_qty = getattr(move, 'quantity_done', getattr(move, 'qty_done', 0.0))
            # sum of quantities already returned by this move
            returned = sum(child.quantity for child in move.returned_move_ids)
            return done_qty - returned

        # 1) Si venimos de una orden de compra, preparamos desde sus recepciones
        if ctx.get('active_model') == 'purchase.order':
            po = self.env['purchase.order'].browse(ctx.get('active_id'))
            pickings = self.env['stock.picking'].search([
                ('purchase_id', '=', po.id),
                ('state', '=', 'done'),
                ('picking_type_id.code', '=', 'incoming'),
            ])
            for pick in pickings:
                for move in pick.move_ids.filtered(lambda m: m.state != 'cancel'):
                    remain = _remaining_qty(move)
                    if remain and remain > 0:
                        lines.append((0, 0, {
                            'move_id': move.id,
                            'quantity': 0.0,
                            'to_refund': False,
                        }))
            res['product_return_moves'] = lines
            return res

        # 2) Si no vienen líneas del stock.return.picking, inicializamos desde el albarán activo
        if 'product_return_moves' in fields_list and not res.get('product_return_moves'):
            picking = self.env['stock.picking'].browse(ctx.get('active_id'))
            for move in picking.move_ids.filtered(lambda m: m.state != 'cancel'):
                remain = _remaining_qty(move)
                if remain and remain > 0:
                    lines.append((0, 0, {
                        'move_id': move.id,
                        'quantity': 0.0,
                        'to_refund': False,
                    }))
            res['product_return_moves'] = lines
        return res

    @api.depends('picking_id')
    def _compute_moves_locations(self):
        for wizard in self:
            product_return_moves = [Command.clear()]
            # Solo pickings validados
            if wizard.picking_id.state != 'done':
                raise UserError(_("Solo se pueden devolver albaranes validados."))
            # Obtener valores por defecto
            line_fields = list(self.env['stock.return.picking.line']._fields)
            default_vals = self.env['stock.return.picking.line'].default_get(line_fields)
            # Recorrer movimientos
            for move in wizard.picking_id.move_ids:
                if move.state == 'cancel':
                    continue
                vals = dict(default_vals)
                vals.update(wizard._prepare_stock_return_picking_line_vals_from_move(move))
                product_return_moves.append(Command.create(vals))
            wizard.product_return_moves = product_return_moves
            _logger.info(
                "  → %d líneas de devolución preparadas para Picking %s",
                len(product_return_moves) - 1,
                wizard.picking_id.name,
            )

    def _create_returns(self):
        # Filtrar solo líneas seleccionadas para devolver
        self.product_return_moves = self.product_return_moves.filtered('to_refund')
        return super()._create_returns()
