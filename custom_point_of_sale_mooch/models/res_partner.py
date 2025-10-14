from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Campos para entrega a domicilio
    delivery_contact_name = fields.Char(string="Nombre de contacto para entrega")
    delivery_phone = fields.Char(string="Teléfono para entrega")
    delivery_address = fields.Text(string="Dirección completa de entrega")
    delivery_notes = fields.Text(string="Notas de entrega")
    delivery_lat = fields.Float(string="Latitud")
    delivery_lng = fields.Float(string="Longitud")
    delivery_maps_url = fields.Char(string="URL de Google Maps")