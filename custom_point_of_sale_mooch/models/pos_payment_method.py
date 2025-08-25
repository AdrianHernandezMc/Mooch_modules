from odoo import models, fields

class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'
    require_transaction_id = fields.Boolean(
        string="Requiere Transaction ID",
        help="Pide capturar el folio cuando se usa este método en el POS."
    )
