from odoo import models, fields, api
from odoo.exceptions import UserError

class purchase_order (models.Model):
  _inherit = 'purchase.order'

  invoice_tag_ids = fields.Many2many(
      'purchase.invoice.tag',
      'purchase_order_invoice_tag_rel',
      'order_id',
      'tag_id',
      string="Facturas Proveedor",
      help="Añade aquí tantas referencias de factura como necesites",
  )