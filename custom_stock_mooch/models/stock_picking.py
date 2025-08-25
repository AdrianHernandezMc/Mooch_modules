from odoo import models, fields, api, _
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

    invoice_order_ids = fields.Many2many(
        'purchase.invoice.tag',  # Mismo modelo que usa la orden de compra
        string="Facturas Proveedor traslados",
        help="Añade aquí tantas referencias de factura como necesites",
    )


    department = fields.Char(
        string='Departamento',
        compute='_compute_department',
        store=True,      # <- si prefieres no almacenarlo, pon False; pero para búsqueda y group_by rinde mejor True
        index=True,
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

    @api.depends('move_ids.product_id.default_code')
    def _compute_department(self):
        PARAM = self.env['barcode.parameter.line']
        PREFIX_LEN = 2
        for pick in self:
            if not pick.move_ids:
                pick.department = _('Sin departamento')
                continue
            code = pick.move_ids[0].product_id.default_code or ''
            prefix = code[:PREFIX_LEN]
            dept = PARAM.search([
                ('parameter_id.name', '=', 'Departamento'),
                ('codigo', '=', prefix),
            ], limit=1)
            pick.department = dept.nombre if dept else _('Sin departamento')

    def write(self, vals):
        # Ejecutar primero el write normal
        result = super(StockPicking, self).write(vals)

        # Si se modificó el campo de facturas, sincronizar con la orden de compra
        if 'invoice_order_ids' in vals:
            self._sync_invoice_tags_to_purchase()

        return result

    @api.model
    def create(self, vals):
        # Crear el picking primero
        picking = super(StockPicking, self).create(vals)

        # Si hay facturas en los valores, sincronizar
        if 'invoice_order_ids' in vals:
            picking._sync_invoice_tags_to_purchase()

        return picking

    def _sync_invoice_tags_to_purchase(self):
        """Sincroniza las facturas del traslado a la orden de compra"""
        for picking in self:
            if picking.purchase_id and picking.invoice_order_ids:
                # Actualizar la orden de compra con las facturas del traslado
                picking.purchase_id.sudo().write({
                    'invoice_tag_ids': [(6, 0, picking.invoice_order_ids.ids)]
                })

    @api.onchange('invoice_order_ids')
    def _onchange_invoice_order_ids(self):
        """Sincroniza inmediatamente cuando se modifican las facturas en la vista"""
        if self.purchase_id and self.invoice_order_ids:
            # Actualizar la orden de compra
            self.purchase_id.invoice_tag_ids = [(6, 0, self.invoice_order_ids.ids)]