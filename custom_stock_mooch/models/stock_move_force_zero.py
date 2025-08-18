# -*- coding: utf-8 -*-
from odoo import api, fields, models

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_confirm(self):
        # Confirmar la OC (crea/actualiza los pickings de recepción)
        res = super().button_confirm()
        # Dejar las recepciones con "Recibida" en 0 solo una vez
        for order in self:
            receipts = order.picking_ids.filtered(
                lambda p: p.picking_type_id.code == 'incoming' and not p.qty_done_zeroed_by_po
            )
            receipts._zero_qty_done_from_po_once()
        return res


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Bandera para no repetir el "reset" en el mismo picking
    qty_done_zeroed_by_po = fields.Boolean(default=False)

    def _zero_qty_done_from_po_once(self):
        """Poner qty_done=0 en líneas de operación de recepciones creadas por la OC (solo una vez)."""
        for p in self:
            # Solo recepciones vivas; si ya está hecho o cerrado, no se toca
            if p.picking_type_id.code != 'incoming' or p.qty_done_zeroed_by_po or p.state in ('done', 'cancel'):
                continue

            # Si por configuración hubiera reservas iniciales, las anulamos (efecto "anular reserva")
            try:
                p.action_unreserve()
            except Exception:
                # No todas las situaciones requieren/permiten unreserve; lo ignoramos si no aplica
                pass

            # Poner en 0 las cantidades hechas (esto es lo que alimenta la columna "Recibida")
            ml = p.move_line_ids
            if ml:
                ml.with_context(skip_tracking=True).write({'qty_done': 0.0})

            # Marcar para no volver a tocar este picking
            p.qty_done_zeroed_by_po = True
