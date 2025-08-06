from odoo import fields, models

class POSLoyaltyReference(models.Model):
    _name = 'pos.loyalty.reference'
    loyalty_card_id = fields.Many2one('loyalty.card', required=True)
    order_id = fields.Many2one('pos.order', required=True)
    product_codes = fields.Char()
