from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    who_transfers = fields.Many2one(
        comodel_name='hr.employee',
        string='Traslada'
    )
    who_receive =  fields.Many2one(
        comodel_name='hr.employee',
        string='Recibe'
    )
    driver = fields.Many2one(
        comodel_name='hr.employee',
        string='Chofer'
    )
    plates = fields.Char(
        string='Placas'
    )
    unity = fields.Char(
        string='Unidad'
    )
    box_quantity = fields.Integer(
        string='Cantidad de cajas',
        default=0
    )

    date_destination_done = fields.Datetime(
        string="Recibido en Destino",
        compute='_compute_date_destination_done',
        readonly=True,
        store=False,
        help="Fecha en que el otro picking (origen o destino) fue validado."
    )

    @api.depends('state', 'origin', 'name')
    def _compute_date_destination_done(self):
        for picking in self:
            date_done_result = False

            # CASO 1: Este picking es el origen (buscamos destino)
            if picking.name:
                dest = self.env['stock.picking'].search([
                    ('origin', '=', picking.name),
                    ('state', '=', 'done'),
                ], limit=1)
                if dest:
                    date_done_result = dest.date_done
                    _logger.info(f"[ORIGEN] {picking.name} => destino: {dest.name}, fecha: {dest.date_done}")

            # CASO 2: Este picking es el destino (buscamos origen)
            if not date_done_result and picking.origin:
                origen = self.env['stock.picking'].search([
                    ('name', '=', picking.origin),
                    ('state', '=', 'done'),
                ], limit=1)
                if origen:
                    date_done_result = origen.date_done
                    _logger.info(f"[DESTINO] {picking.name} => origen: {origen.name}, fecha: {origen.date_done}")

            picking.date_destination_done = date_done_result