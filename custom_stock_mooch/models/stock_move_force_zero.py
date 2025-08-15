from odoo import api, models

class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for m in moves:
            # Solo recepciones (compras) e internas
            if m.picking_id and m.picking_id.picking_type_id.code in ('incoming', 'internal'):
                # Si vino con quantity ya seteada, la respetamos; si no, a 0
                if not m.quantity:
                    m.quantity = 0.0
        return moves

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    @api.model_create_multi
    def create(self, vals_list):
        # Respetar escaneo: si ya pasan qty_done en vals, no lo tocamos
        for v in vals_list:
            if 'qty_done' not in v:
                v['qty_done'] = 0.0
        return super().create(vals_list)
