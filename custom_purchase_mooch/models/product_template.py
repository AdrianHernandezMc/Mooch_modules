from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string="Cuenta Analítica",
        related='categ_id.computed_analytic_account_id',
        store=True,
        readonly=False,
        help="Tomada de la categoría de productos(si no tiene notificar).",
    )
