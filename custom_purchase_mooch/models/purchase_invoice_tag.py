from odoo import models, fields

class PurchaseInvoiceTag(models.Model):
    _name = 'purchase.invoice.tag'
    _description = 'Etiqueta de Número de Factura Proveedor'

    name = fields.Char(string="Referencia de Factura", required=True)