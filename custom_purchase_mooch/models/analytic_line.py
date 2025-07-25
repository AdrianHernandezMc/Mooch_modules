# -*- coding: utf-8 -*-
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class AnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    @api.model_create_multi
    def create(self, vals_list):
        # 1) Crea primero los registros con lógica original (solo neto)
        recs = super().create(vals_list)

        # 2) Agrupa las líneas nuevas por factura (move_id)
        inv_groups = {}
        for rec in recs:
            inv = getattr(rec.move_line_id, 'move_id', False)
            if inv and inv.move_type in ('in_invoice', 'in_refund'):
                inv_groups.setdefault(inv, []).append(rec)

        # 3) Por cada factura, prorratea el IVA entre sus líneas
        for inv, lines in inv_groups.items():
            # Mapa de neto por cuenta analítica
            net_map = {}
            for rec in lines:
                net_map.setdefault(rec.account_id.id, 0.0)
                net_map[rec.account_id.id] += abs(rec.amount)

            total_net = sum(net_map.values())
            # Determina el signo del IVA (factura de proveedor = costo → IVA negativo)
            tax_amt = inv.amount_tax or 0.0
            if inv.move_type == 'in_invoice':
                tax_amt = -abs(tax_amt)
            else:
                tax_amt = abs(tax_amt)

            # 4) Ajusta cada línea
            for rec in lines:
                prev = rec.amount
                if total_net:
                    share = tax_amt * (abs(prev) / total_net)
                else:
                    share = 0.0
                new_amount = prev + share
                # Redondea con la moneda de la línea
                rec.amount = rec.currency_id.round(new_amount)
                _logger.info(
                    "🔄 AnalyticLine %s: net=%s IVA_share=%s → amount=%s",
                    rec.id, prev, share, rec.amount
                )

        return recs
