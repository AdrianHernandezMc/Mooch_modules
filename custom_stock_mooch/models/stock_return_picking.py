import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.models import Command

_logger = logging.getLogger(__name__)

class StockReturnPickingLine(models.TransientModel):
    _inherit = 'stock.return.picking.line'

    to_refund = fields.Boolean(string="Seleccionar", default=False)

class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        lines = []

        def _remaining_qty(move):
            done_qty = getattr(move, 'quantity_done', getattr(move, 'qty_done', 0.0))
            returned = sum(child.quantity for child in move.returned_move_ids)
            return max(0, done_qty - returned)

        # 1) Lógica desde PURCHASE ORDER
        if ctx.get('active_model') == 'purchase.order':
            po = self.env['purchase.order'].browse(ctx.get('active_id'))
            # OJO: Esto asume que queremos devolver cosas de varios pickings
            # pero el wizard solo soporta UN picking padre a la vez para la cabecera.
            # Tomamos el último picking validado como referencia para la cabecera
            last_picking = self.env['stock.picking'].search([
                ('purchase_id', '=', po.id),
                ('state', '=', 'done'),
                ('picking_type_id.code', '=', 'incoming'),
            ], order='date_done desc', limit=1)

            if last_picking:
                res['picking_id'] = last_picking.id

            pickings = self.env['stock.picking'].search([
                ('purchase_id', '=', po.id),
                ('state', '=', 'done'),
                ('picking_type_id.code', '=', 'incoming'),
            ])

            for pick in pickings:
                for move in pick.move_ids.filtered(lambda m: m.state != 'cancel'):
                    remain = _remaining_qty(move)
                    if remain > 0:
                        lines.append((0, 0, {
                            'product_id': move.product_id.id, # Es necesario pasar producto
                            'move_id': move.id,
                            'quantity': remain, # Sugerir el total restante por defecto
                            'to_refund': False, # El usuario debe marcar explícitamente
                        }))
            res['product_return_moves'] = lines
            return res

        return res

    @api.depends('picking_id')
    def _compute_moves_locations(self):
        # EVITAR que este compute borre las líneas si venimos del contexto de PO
        if self.env.context.get('active_model') == 'purchase.order':
            return

        for wizard in self:
            # Lógica original o tu lógica custom para standard pickings
            product_return_moves = [Command.clear()]
            if wizard.picking_id.state != 'done':
                 # Permitir que falle silenciosamente o manejar error
                 continue

            line_fields = list(self.env['stock.return.picking.line']._fields)
            default_vals = self.env['stock.return.picking.line'].default_get(line_fields)

            for move in wizard.picking_id.move_ids:
                if move.state == 'cancel':
                    continue
                vals = dict(default_vals)
                vals.update(wizard._prepare_stock_return_picking_line_vals_from_move(move))
                # Inicializar en False para obligar a seleccionar
                vals['to_refund'] = False
                product_return_moves.append(Command.create(vals))

            wizard.product_return_moves = product_return_moves

    def _create_returns(self):
        # Validar que haya al menos una línea seleccionada
        to_return = self.product_return_moves.filtered('to_refund')
        if not to_return:
            raise UserError(_("Por favor, selecciona al menos una línea para devolver ('Seleccionar')."))

        # Validar cantidades
        if any(line.quantity <= 0 for line in to_return):
            raise UserError(_("Las líneas seleccionadas deben tener una cantidad mayor a 0."))

        # Filtrar el recordset para que el super solo procese las marcadas
        self.product_return_moves = to_return

        return super()._create_returns()