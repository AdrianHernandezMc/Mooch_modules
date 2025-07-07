from odoo import models, fields, api

class ProductCategory(models.Model):
    _inherit = 'product.category'

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string="Cuenta Analítica",
        help="Si no se pone, hereda la de la categoría padre",
    )
    computed_analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string="Cuenta Analítica (heredada)",
        compute='_compute_computed_analytic_account_id',
        store=True,
        help="Cuenta propia o, si no, la de la categoría padre",
    )

    @api.depends('analytic_account_id', 'parent_id.computed_analytic_account_id')
    def _compute_computed_analytic_account_id(self):
        for cat in self:
            cat.computed_analytic_account_id = (
                cat.analytic_account_id
                or (cat.parent_id.computed_analytic_account_id if cat.parent_id else False)
            )