from odoo import models, fields, api
from odoo.exceptions import UserError

class purchase_order (models.Model):
  _inherit = 'purchase.order'

  invoice_id =fields.Char(String="Numero de factura proveedor",
                          help="Ingresar numero de fectura de porveedor",
                          store=True,
                          tracking=True,
                          )