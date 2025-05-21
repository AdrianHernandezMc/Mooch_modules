from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    cuenta_cliente_mooch = fields.Char(string="Cuenta Cliente")
    cuenta_adicional_mooch = fields.Char(string="Cuenta Adicional")
    nombre_mooch = fields.Char(string="Nombre")
    paterno_mooch = fields.Char(string="Paterno")
    materno_mooch = fields.Char(string="Materno")
    limcred_mooch = fields.Monetary(string="Límite de crédito", currency_field='currency_id')
    saldo_disponible_mooch = fields.Monetary(string="Saldo disponible", currency_field='currency_id')
