from odoo import models, fields

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    quant_rack_area = fields.Char(string="Rack / Área")

    def _get_inventory_move_values(self, *args, **kwargs):
        """
        No tocamos los argumentos de entrada.
        Dejamos que Odoo haga su trabajo y solo modificamos el resultado final.
        """
        # 1. Llamamos al original pasándole TODO lo que reciba (sea lo que sea)
        res = super()._get_inventory_move_values(*args, **kwargs)

        if self.quant_rack_area:
            if res.get('move_line_ids'):
                try:
                    res['move_line_ids'][0][2]['quant_rack_area'] = self.quant_rack_area
                except IndexError:
                    pass
        return res