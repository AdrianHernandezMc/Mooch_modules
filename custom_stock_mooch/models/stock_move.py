from odoo import models, api, _ , fields
from odoo.tools import float_compare

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
            # Opcional: omitir movimientos "negativos" o cero (devoluciones), igual que hace Odoo
            if float_compare(move.product_uom_qty, 0.0, precision_rounding=move.product_uom.rounding) <= 0:
                continue
            # Preparar valores para la nueva transferencia
            picking_vals = move._get_new_picking_values()
            # Crear un nuevo picking para este movimiento
            new_picking = StockPicking.create(picking_vals)
            # Asignar el movimiento al nuevo picking
            move.write({'picking_id': new_picking.id})
            # Llamar a la post-procesamiento estándar (reservas, backorders, etc.)
            move._assign_picking_post_process(new=True)
        return True

    @api.depends('product_id.product_tmpl_id.department_id.name')
    def _compute_department_name(self):
        for move in self:
            move.department_name = move.product_id.product_tmpl_id.department_id.name or ''