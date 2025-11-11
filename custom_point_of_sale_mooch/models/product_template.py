from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Campo computado para traslados pendientes de POS
    pending_pos_pickings_count = fields.Integer(
        string='Traslados POS Pendientes',
        compute='_compute_pending_pos_pickings',
        store=False
    )

    def _compute_pending_pos_pickings(self):
        for template in self:
            # Buscar picking pendientes de POS para los productos de este template
            product_ids = template.product_variant_ids.ids
            if product_ids:
                pending_pickings = self.env['stock.picking'].search([
                    ('pos_order_id', '!=', False),
                    ('state', 'not in', ['done', 'cancel']),
                    ('move_ids.product_id', 'in', product_ids)
                ])
                template.pending_pos_pickings_count = len(pending_pickings)
            else:
                template.pending_pos_pickings_count = 0

    def action_view_pending_pos_pickings(self):
        """Abrir vista de traslados pendientes para este template"""
        self.ensure_one()
        
        product_ids = self.product_variant_ids.ids
        if not product_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'message': 'No hay variantes de producto.',
                }
            }
        
        pending_pickings = self.env['stock.picking'].search([
            ('pos_order_id', '!=', False),
            ('state', 'not in', ['done', 'cancel']),
            ('move_ids.product_id', 'in', product_ids)
        ])
        
        if not pending_pickings:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'message': 'No hay traslados pendientes de POS para este producto.',
                }
            }
            
        return {
            'type': 'ir.actions.act_window',
            'name': f'Traslados POS Pendientes - {self.name}',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', pending_pickings.ids)],
            'context': {
                'search_default_pos_order_id': True,
                'search_default_product_id': self.product_variant_ids[0].id if self.product_variant_ids else False,
            },
        }