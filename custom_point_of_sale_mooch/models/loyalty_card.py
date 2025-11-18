# -*- coding: utf-8 -*-
from odoo import api,models, fields

class LoyaltyCard(models.Model):
    _inherit = "loyalty.card"

    pos_reference = fields.Char(
        string="POS Reference",
        help="Referencia de la orden POS vinculada a esta tarjeta."
    )

    @api.model
    def sync_source_order_by_posref(self, limit=1000):
        cards = self.search([
            ("source_pos_order_id", "=", False),
            ("pos_reference", "!=", False),
        ], limit=limit)

        if not cards:
            return {"updated": 0}

        refs = list(set(cards.mapped("pos_reference")))
        orders = self.env["pos.order"].search([("pos_reference", "in", refs)])
        ref2id = {o.pos_reference: o.id for o in orders}

        updated = 0

        # Escribe por lotes
        for c in cards:
            oid = ref2id.get(c.pos_reference)
            if oid:
                c.write({"source_pos_order_id": oid})
                updated += 1
        return {"updated": updated}

    # ==============================
    #   CONTROL DE CONSUMO DEL VALE
    # ==============================

    def write(self, vals):
        """
        Intercepta cambios en 'points':
        - Si Odoo intenta bajar puntos (consumo parcial)
        - Y la tarjeta está ligada a una venta POS (pos_reference)
        => Forzamos que se consuman TODOS los puntos (0) y la marcamos como 'redeemed'.
        """
        for card in self:
            local_vals = dict(vals)  # copia para este registro

            if "points" in local_vals:
                old_points = card.points
                # convertir a número lo que viene en vals
                try:
                    new_points = float(local_vals["points"])
                except (TypeError, ValueError):
                    new_points = old_points

                # Solo actuamos si:
                #  - la tarjeta viene de POS (tiene pos_reference)
                #  - y se está BAJANDO el saldo de puntos (consumo)
                if card.pos_reference and new_points < old_points:
                    # 🔥 Forzar consumo completo
                    local_vals["points"] = 0

                    # Si existe campo 'state', la marcamos como redimida
                    if "state" in card._fields and not local_vals.get("state"):
                        # Ajusta según tus estados: 'redeemed', 'used', etc.
                        local_vals["state"] = "redeemed"

            # Hacemos write usando los vals ajustados SOLO para este card
            super(LoyaltyCard, card).write(local_vals)

        return True