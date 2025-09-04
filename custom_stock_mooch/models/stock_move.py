# -*- coding: utf-8 -*-
from odoo import models, api, _ , fields
from odoo.tools import float_compare
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    department_name = fields.Char(
        string='Departamento',
        store=True,
        compute='_compute_department_name',
    )

    def _assign_picking(self):
        """Override to avoid grouping: each stock.move -> its own picking."""
        StockPicking = self.env['stock.picking']
        for move in self:  # iterar por cada movimiento individualmente
            if float_compare(move.product_uom_qty, 0.0, precision_rounding=move.product_uom.rounding) <= 0:
                continue
            picking_vals = move._get_new_picking_values()
            new_picking = StockPicking.create(picking_vals)
            move.write({'picking_id': new_picking.id})
            move._assign_picking_post_process(new=True)
        return True

    @api.depends('product_id.product_tmpl_id.department_id.name')
    def _compute_department_name(self):
        for move in self:
            move.department_name = move.product_id.product_tmpl_id.department_id.name or ''

    # --- Hook: cuando se crean/escriben líneas de RECEPCIÓN, intentamos reubicar ---
    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        pickings = moves.mapped('picking_id').filtered(
            lambda p: p and p.picking_type_code == 'incoming' and p.state not in ('done', 'cancel')
        )
        for p in pickings:
            try:
                p._auto_set_destination_on_receipt()
            except Exception as e:
                _logger.debug("Auto destino desde move.create %s: %s", p.name or p.id, e)
        return moves

    def write(self, vals):
        res = super().write(vals)
        if {'product_id', 'location_dest_id', 'picking_id'} & set(vals.keys()):
            pickings = self.mapped('picking_id').filtered(
                lambda p: p and p.picking_type_code == 'incoming' and p.state not in ('done', 'cancel')
            )
            for p in pickings:
                try:
                    p._auto_set_destination_on_receipt()
                except Exception as e:
                    _logger.debug("Auto destino desde move.write %s: %s", p.name or p.id, e)
        return res

    def check_quantity_exceeded(self):
        """Método para verificar cantidades excedidas"""
        exceeded_moves = []
        for move in self:
            # Calcular la cantidad realizada sumando las líneas
            qty_done = sum(move.move_line_ids.mapped('qty_done'))
            if qty_done > move.product_uom_qty:
                exceeded_moves.append({
                    'product': move.product_id.display_name,
                    'demanded': move.product_uom_qty,
                    'received': qty_done,
                    'excess': qty_done - move.product_uom_qty
                })
        return exceeded_moves

    def _action_done(self, cancel_backorder=False):
        # Validación completa antes de procesar
        exceeded_moves = self.check_quantity_exceeded()
        
        if exceeded_moves:
            error_message = _("No se puede validar la transferencia. Los siguientes productos exceden la cantidad demandada:\n\n")
            for move_data in exceeded_moves:
                error_message += _("• %s: Solicitado %s, Recibido %s (Exceso: %s)\n") % (
                    move_data['product'], 
                    move_data['demanded'], 
                    move_data['received'], 
                    move_data['excess']
                )
            
            raise ValidationError(error_message)
        
        return super(StockMove, self)._action_done(cancel_backorder)

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    @api.constrains('qty_done')
    def _check_qty_done_not_exceed(self):
        """Validación en tiempo real en las líneas"""
        for line in self:
            if line.move_id and line.qty_done > line.move_id.product_uom_qty:
                raise ValidationError(_(
                    "¡Cantidad excedida en línea!\n"
                    "Producto: %s\n"
                    "No puede recibir %s cuando la cantidad demandada es %s"
                ) % (line.product_id.display_name, 
                     line.qty_done, 
                     line.move_id.product_uom_qty))