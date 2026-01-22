from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    x_transfer_number = fields.Char(
        string='Número de Transferencia',
        required=True,
        default='No asignado',
        help='Referencia de la transferencia bancaria.'
    )
    x_payment_method_mode = fields.Selection(
        selection=[
            ('TBD', 'TBD - Por definir'),
            ('PUE', 'PUE - Pago en una sola exhibición'),
            ('PPD', 'PPD - Pago en parcialidades o diferido')
        ],
        string='Método de Pago',
        default='TBD',
        required=True,
        help='Selecciona si es Pago en Una sola Exhibición o en Parcialidades.'
    )
    x_is_provisioned = fields.Boolean(
        string='¿Provisionado?',
        default=False,
        help='Marcar si esta factura ya ha sido provisionada correctamente.'
    )
    x_is_complete = fields.Boolean(
        string='¿Completo?',
        default=False,
        help='Marcar si esta factura ya ha sido ya tiene completa toda sus notas y complementos.'
    )