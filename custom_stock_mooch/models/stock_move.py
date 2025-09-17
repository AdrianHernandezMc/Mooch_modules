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
        # Validación completa antes de procesar - SOLO ADVERTENCIA, NO ERROR
        exceeded_moves = self.check_quantity_exceeded()
        
        if exceeded_moves:
            # Mensaje formateado con saltos de línea y formato limpio
            warning_message = _("⚠️ ADVERTENCIA: Los siguientes productos exceden la cantidad demandada:\n\n")
            
            for i, move_data in enumerate(exceeded_moves, 1):
                warning_message += _("➡️ Producto %d: %s\n") % (i, move_data['product'])
                warning_message += _("   • Solicitado: %s\n") % move_data['demanded']
                warning_message += _("   • Recibido: %s\n") % move_data['received']
                warning_message += _("   • Exceso: %s\n\n") % move_data['excess']
            
            # Mensaje alternativo más compacto
            compact_message = _("⚠️ ADVERTENCIA: Productos con exceso de cantidad:\n\n")
            for move_data in exceeded_moves:
                compact_message += _("• %s: %s → %s (+%s)\n") % (
                    move_data['product'], 
                    move_data['demanded'], 
                    move_data['received'], 
                    move_data['excess']
                )
            
            # Mostrar advertencia en el log
            _logger.warning("="*80)
            _logger.warning("ADVERTENCIA DE CANTIDAD EXCEDIDA")
            _logger.warning("="*80)
            _logger.warning(compact_message)
            _logger.warning("="*80)
            
            # Forzar el mensaje en la interfaz mediante el picking relacionado
            pickings = self.mapped('picking_id')
            for picking in pickings:
                picking.message_post(
                    body=warning_message,
                    subject=_("⚠️ Advertencia: Cantidades excedidas"),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note'
                )
    
        return super(StockMove, self)._action_done(cancel_backorder)

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _show_warning_notification(self, message, title):
        """Método para mostrar notificaciones de advertencia"""
        # Registrar en log
        _logger.warning("%s: %s", title, message)
        
        # Intentar mostrar notificación usando varios métodos
        try:
            # Método 1: Usar bus.bus si está disponible
            if hasattr(self.env['bus.bus'], '_sendone'):
                self.env['bus.bus']._sendone(
                    self.env.user.partner_id,
                    'display_notification',
                    {
                        'type': 'warning',
                        'title': title,
                        'message': message,
                        'sticky': False,
                    }
                )
                return True
        except Exception as e:
            _logger.debug("Método bus.bus falló: %s", e)
        
        try:
            # Método 2: Crear un mensaje en el chatter del usuario
            self.env.user.partner_id.message_post(
                body=message,
                subject=title,
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )
            return True
        except Exception as e:
            _logger.debug("Método message_post falló: %s", e)
        
        return False

    @api.constrains('qty_done')
    def _check_qty_done_not_exceed(self):
        """Validación en tiempo real en las líneas - SOLO ADVERTENCIA, NO ERROR"""
        for line in self:
            if line.move_id and line.qty_done > line.move_id.product_uom_qty:
                warning_message = _(
                    "¡ADVERTENCIA: Cantidad excedida en línea!\n"
                    "Producto: %s\n"
                    "Se está recibiendo %s cuando la cantidad demandada es %s"
                ) % (line.product_id.display_name, 
                     line.qty_done, 
                     line.move_id.product_uom_qty)
                
                self._show_warning_notification(
                    warning_message, 
                    _("Advertencia de cantidad")
                )