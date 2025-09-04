# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    who_transfers = fields.Many2one('hr.employee', string='Traslada')
    who_receive   = fields.Many2one('hr.employee', string='Recibe')
    driver        = fields.Many2one('hr.employee', string='Chofer')
    plates        = fields.Char(string='Placas')
    unity         = fields.Char(string='Unidad')
    box_quantity  = fields.Integer(string='Cantidad de cajas', default=0)

    date_destination_done = fields.Datetime(
        string="Recibido en Destino",
        compute='_compute_date_destination_done',
        readonly=True,
        store=False,
        help="Fecha en que el otro picking (origen o destino) fue validado."
    )

    invoice_order_ids = fields.Many2many(
        'purchase.invoice.tag',
        string="Facturas Proveedor traslados",
        help="Añade aquí tantas referencias de factura como necesites",
        required=True,
    )

    # >>> Tu campo/compute existente (NO se cambia la lógica).
    department = fields.Char(
        string='Departamento',
        compute='_compute_department',
        store=True,
        index=True,
    )

    # =============================
    # Computes
    # =============================
    @api.depends('state', 'origin', 'name')
    def _compute_date_destination_done(self):
        for picking in self:
            date_done_result = False

            if picking.name:
                dest = self.env['stock.picking'].search([
                    ('origin', '=', picking.name), ('state', '=', 'done')
                ], limit=1)
                if dest:
                    date_done_result = dest.date_done
                    _logger.info("[ORIGEN] %s => destino: %s, fecha: %s",
                                 picking.name, dest.name, dest.date_done)

            if not date_done_result and picking.origin:
                origen = self.env['stock.picking'].search([
                    ('name', '=', picking.origin), ('state', '=', 'done')
                ], limit=1)
                if origen:
                    date_done_result = origen.date_done
                    _logger.info("[DESTINO] %s => origen: %s, fecha: %s",
                                 picking.name, origen.name, origen.date_done)

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

    # =============================
    # Create / Write
    # =============================
    @api.model
    def create(self, vals):
        picking = super().create(vals)
        # Solo recepciones; si aún no hay líneas/department, no hace nada.
        try:
            picking._auto_set_destination_on_receipt()
        except Exception as e:
            _logger.debug("Auto destino recepción (create) %s: %s", picking.display_name, e)

        if 'invoice_order_ids' in vals:
            picking._sync_invoice_tags_to_purchase()
        return picking

    def write(self, vals):
        res = super().write(vals)

        # Reintentar SOLO en recepciones (incoming) y no done/cancel
        if {'name', 'move_ids', 'move_line_ids', 'location_dest_id', 'location_id', 'state', 'picking_type_id'} & set(vals.keys()):
            for picking in self.filtered(lambda p: p.picking_type_code == 'incoming' and p.state not in ('done', 'cancel')):
                try:
                    picking._auto_set_destination_on_receipt()
                except Exception as e:
                    _logger.debug("Auto destino recepción (write) %s: %s", picking.display_name, e)

        if 'invoice_order_ids' in vals:
            self._sync_invoice_tags_to_purchase()
        return res

    # =============================
    # Onchange (visual en formulario)
    # =============================
    @api.onchange('name', 'location_id', 'move_ids_without_package', 'move_ids_without_package.product_id')
    def _onchange_auto_destination(self):
        for picking in self:
            if picking.picking_type_code != 'incoming':
                continue
            dest = picking._compute_department_destination_location()
            if dest and picking.location_dest_id != dest:
                picking.location_dest_id = dest

    # =============================
    # Sincronía facturas -> OC
    # =============================
    def _sync_invoice_tags_to_purchase(self):
        for picking in self:
            if picking.purchase_id and picking.invoice_order_ids:
                picking.purchase_id.sudo().write({
                    'invoice_tag_ids': [(6, 0, picking.invoice_order_ids.ids)]
                })

    @api.onchange('invoice_order_ids')
    def _onchange_invoice_order_ids(self):
        if self.purchase_id and self.invoice_order_ids:
            self.purchase_id.invoice_tag_ids = [(6, 0, self.invoice_order_ids.ids)]

    # =============================
    # Núcleo: SOLO Recepciones
    # =============================
    def _auto_set_destination_on_receipt(self):
        """Ajusta destino a <ROOT_DESDE>/<DEPARTAMENTO> solo si:
           - picking_type_code == 'incoming'
           - no está done/cancel
           - 'Desde' (location_id) NO es Vendors (usage='supplier')
        """
        for picking in self:
            if picking.picking_type_code != 'incoming' or picking.state in ('done', 'cancel'):
                continue

            dest = picking._compute_department_destination_location()
            if not dest or picking.location_dest_id == dest:
                continue

            _logger.info("Reubicando destino recepción %s → %s",
                         picking.name or picking.id, dest.complete_name)

            picking.location_dest_id = dest.id
            # moves abiertos
            picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')).write({
                'location_dest_id': dest.id
            })
            # move lines abiertas
            picking.move_line_ids.filtered(lambda ml: getattr(ml, 'state', False) not in ('done', 'cancel')).write({
                'location_dest_id': dest.id
            })

    # ---------- Helpers ----------
    def _get_department_text(self):
        self.ensure_one()
        val = getattr(self, 'department', False)
        if not val:
            return False
        if isinstance(val, str):
            return val.strip()
        name = getattr(val, 'name', False) or getattr(val, 'display_name', False)
        return (name or '').strip() if name else False

    def _get_root_from_desde(self):
        """Raíz a partir de 'Desde' (location_id).
        - Si location_id.usage == 'supplier' (Partners/Vendors) → NO aplicar.
        - Si es interna o vista, sube a la raíz (sin parent).
        """
        self.ensure_one()
        loc = self.location_id
        if not loc:
            return False
        # Ignorar Vendors
        if getattr(loc, 'usage', False) == 'supplier':
            return False
        # Subir hasta la raíz
        while loc.location_id:
            loc = loc.location_id
        return loc

    def _find_department_location_under(self, root, dept):
        Location = self.env['stock.location']

        # Preferir por complete_name "ROOT/DEPTO%"
        dest = Location.search([
            ('id', 'child_of', root.id),
            ('usage', '=', 'internal'),
            ('complete_name', 'ilike', f"{root.name}/{dept}%"),
        ], limit=1)
        if not dest:
            # Segundo intento por name exacto/ilike del nodo hoja
            dest = Location.search([
                ('id', 'child_of', root.id),
                ('usage', '=', 'internal'),
                ('name', 'ilike', dept),
            ], limit=1)
        return dest

    def _compute_department_destination_location(self):
        """Calcula (NO escribe) la ubicación destino correcta o False.
           Regla: SOLO si es recepción y 'Desde' NO es Vendors.
           Raíz = raíz de `location_id` (Desde).
           Destino = sububicación interna '<root>/<department>'.
        """
        self.ensure_one()
        if self.picking_type_code != 'incoming':
            return False

        # 1) Ignorar si 'Desde' es Vendors
        root = self._get_root_from_desde()
        if not root:
            return False

        # 2) Tomar el texto de departamento
        dept = self._get_department_text()
        if not dept or dept.lower().strip().startswith('sin'):
            return False

        # 3) Buscar sububicación bajo la raíz de 'Desde'
        return self._find_department_location_under(root, dept) or False
