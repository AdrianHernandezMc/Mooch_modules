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