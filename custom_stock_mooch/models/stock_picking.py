from odoo import models, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    who_transfers = fields.Many2one(
        comodel_name='hr.employee',
        string='Traslada')
    who_receive =  fields.Many2one(
        comodel_name='hr.employee',
        string='Recibe'
    )
    driver = fields.Many2one(
        comodel_name='hr.employee',
        string='Chofer'
    )