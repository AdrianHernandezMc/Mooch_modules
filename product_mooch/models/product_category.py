from odoo import models, api

class ProductCategory(models.Model):
    _inherit = 'product.category'

    @api.model
    def create(self, vals):
        vals['property_cost_method'] = 'average'
        return super(ProductCategory, self).create(vals)
