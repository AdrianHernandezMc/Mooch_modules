# -*- coding: utf-8 -*-
from odoo import models, api, _ , fields
from odoo.tools import float_compare
import logging

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
