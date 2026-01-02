# -*- coding: utf-8 -*-
from odoo import models, api, _ , fields
from odoo.tools import float_compare
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    department_name = fields.Char(
        string='Departamento',
        store=True,
        compute='_compute_department_name',
    )

    def _assign_picking(self):
        """
        Sobreescritura corregida:
        1. Agrupa movimientos actuales.
        2. Busca pickings recientes (24h) ignorando si el destino ya cambió por la lógica de departamentos.
        """
        StockPicking = self.env['stock.picking']
        grouped_moves = {}

        # 1. Agrupar los movimientos que vienen en este proceso (self)
        for move in self:
            if move.picking_id or float_compare(move.product_uom_qty, 0.0, precision_rounding=move.product_uom.rounding) <= 0:
                continue

            # Clave de agrupación interna para este lote
            key = (
                move.picking_type_id.id,
                move.location_id.id,
                move.location_dest_id.id,
                move.partner_id.id,
                move.origin,
                move.group_id.id
            )
            if key not in grouped_moves:
                grouped_moves[key] = self.env['stock.move']
            grouped_moves[key] |= move

        # 2. Procesar cada grupo e intentar unirlo a un picking existente
        for key, moves in grouped_moves.items():
            picking_type_id, location_id, location_dest_id, partner_id, origin, group_id = key
            
            # --- CAMBIO CRÍTICO AQUÍ ---
            # Quitamos 'location_dest_id' del dominio de búsqueda.
            # Esto permite que si el picking existente ya cambió de destino (por departamento),
            # las nuevas líneas aún puedan encontrarlo y unirse.
            domain = [
                ('picking_type_id', '=', picking_type_id),
                ('location_id', '=', location_id),
                # ('location_dest_id', '=', location_dest_id),  <-- ELIMINADO PARA PERMITIR UNIÓN
                ('partner_id', '=', partner_id),
                ('state', 'in', ['draft', 'confirmed', 'assigned', 'waiting']),
                ('create_date', '>=', fields.Datetime.now() - timedelta(hours=24))
            ]
            
            if origin:
                domain.append(('origin', '=', origin))
            else:
                domain.append(('origin', '=', False))
                
            if group_id:
                domain.append(('group_id', '=', group_id))

            # Buscar picking existente
            picking = StockPicking.search(domain, limit=1)

            if picking:
                _logger.info("Uniendo movimientos al picking existente: %s", picking.name)
                moves.write({'picking_id': picking.id})
                moves._assign_picking_post_process(new=False)
            else:
                # Crear uno nuevo
                vals = moves[0]._get_new_picking_values()
                picking = StockPicking.create(vals)
                _logger.info("Creando nuevo picking: %s", picking.name)
                moves.write({'picking_id': picking.id})
                moves._assign_picking_post_process(new=True)

        return True

    @api.depends('product_id.product_tmpl_id.department_id.name')
    def _compute_department_name(self):
        for move in self:
            move.department_name = move.product_id.product_tmpl_id.department_id.name or ''

    # --- Hook: cuando se crean/escriben líneas de RECEPCIÓN, intentamos reubicar ---
    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        
        # Validar que picking_type_id exista antes de acceder a code
        incoming_moves = moves.filtered(lambda m: m.picking_type_id and m.picking_type_id.code == 'incoming')
        
        if incoming_moves:
            pickings = incoming_moves.mapped('picking_id').filtered(
                lambda p: p.state not in ('done', 'cancel')
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
            
            # Validar que picking_type_id exista antes de acceder a code
            incoming_moves = self.filtered(lambda m: m.picking_type_id and m.picking_type_id.code == 'incoming')
            
            if incoming_moves:
                pickings = incoming_moves.mapped('picking_id').filtered(
                    lambda p: p.state not in ('done', 'cancel')
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
            # Mensaje formateado
            warning_message = _("⚠️ ADVERTENCIA: Los siguientes productos exceden la cantidad demandada:\n\n")
            
            for i, move_data in enumerate(exceeded_moves, 1):
                warning_message += _("➡️ Producto %d: %s\n") % (i, move_data['product'])
                warning_message += _("   • Solicitado: %s\n") % move_data['demanded']
                warning_message += _("   • Recibido: %s\n") % move_data['received']
                warning_message += _("   • Exceso: %s\n\n") % move_data['excess']
            
            compact_message = _("⚠️ ADVERTENCIA: Productos con exceso de cantidad:\n\n")
            for move_data in exceeded_moves:
                compact_message += _("• %s: %s → %s (+%s)\n") % (
                    move_data['product'], 
                    move_data['demanded'], 
                    move_data['received'], 
                    move_data['excess']
                )
            
            _logger.warning("="*80)
            _logger.warning("ADVERTENCIA DE CANTIDAD EXCEDIDA")
            _logger.warning("="*80)
            _logger.warning(compact_message)
            _logger.warning("="*80)
            
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
        _logger.warning("%s: %s", title, message)
        try:
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