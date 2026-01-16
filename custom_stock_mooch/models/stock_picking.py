# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # ---- Tus campos existentes (se dejan tal cual) ----
    who_transfers = fields.Many2one('hr.employee', string='Traslada')
    who_receive   = fields.Many2one('hr.employee', string='Recibe', required=True)
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
    )

    # Departamento (tu compute; no lo modifico)
    department = fields.Char(
        string='Departamento',
        compute='_compute_department',
        store=True,
        index=True,
    )

    # ---- NUEVO: bandera para aplicar el destino por depto SOLO la primera vez ----
    dept_dest_applied = fields.Boolean(
        string='Destino por departamento aplicado',
        default=False,
        copy=False,  # en backorders arranca False y lo ponemos explícitamente
    )

    purchase_qty_zeroed = fields.Boolean(
        string='Qty done en 0 (compras)',
        default=False,
        copy=False,
        help="Marca que ya se puso qty_done=0 por primera vez en esta recepción de compra."
    )

    # =============================
    # Computes (tuyos)
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
        # SOLO la primera vez que se crea el picking incoming
        try:
            picking._auto_set_destination_on_receipt(first_time_only=True)
        except Exception as e:
            _logger.debug("Auto destino recepción (create) %s: %s", picking.display_name, e)

        if 'invoice_order_ids' in vals:
            picking._sync_invoice_tags_to_purchase()
        return picking

    def write(self, vals):
        res = super().write(vals)
        # Si aún no se ha aplicado y es recepción, intentamos aplicarlo
        if {'name', 'move_ids', 'move_line_ids', 'location_dest_id', 'location_id', 'state', 'picking_type_id'} & set(vals.keys()):
            for picking in self.filtered(lambda p: p.picking_type_code == 'incoming' and p.state not in ('done', 'cancel')):
                try:
                    picking._auto_set_destination_on_receipt(first_time_only=True)
                except Exception as e:
                    _logger.debug("Auto destino recepción (write) %s: %s", picking.display_name, e)

        if 'invoice_order_ids' in vals:
            self._sync_invoice_tags_to_purchase()
        return res

    # =============================
    # Backorders: heredar ubicación destino por departamento
    # =============================
    def _create_backorder(self):
        backorders = super()._create_backorder()

        for bo in backorders.filtered(lambda b: b.picking_type_code == 'incoming' and b.state not in ('done', 'cancel')):
            try:
                # 1) ¿Es backorder de COMPRA?
                is_purchase = bool(bo.purchase_id or (bo.backorder_id and bo.backorder_id.purchase_id))
                if is_purchase:
                    # Dejar TODAS las operaciones del backorder en 0 (primer arranque)
                    if bo.move_line_ids:
                        bo.move_line_ids.write({'qty_done': 0.0})
                    # Si usas el flag sugerido
                    if hasattr(bo, 'purchase_qty_zeroed') and not bo.purchase_qty_zeroed:
                        bo.purchase_qty_zeroed = True

                # 2) Destino por Departamento: heredar o recalcular
                orig = bo.backorder_id
                if orig and orig.location_dest_id:
                    # Hereda destino del original
                    bo.location_dest_id = orig.location_dest_id.id
                    # Alinear moves/lines abiertos
                    bo.move_ids.filtered(lambda m: m.state not in ('done','cancel')).write({
                        'location_dest_id': bo.location_dest_id.id
                    })
                    bo.move_line_ids.filtered(lambda l: getattr(l, 'state', False) not in ('done','cancel')).write({
                        'location_dest_id': bo.location_dest_id.id
                    })
                    if hasattr(bo, 'dept_dest_applied'):
                        bo.dept_dest_applied = True
                else:
                    # Recalcular por departamento bajo la raíz correcta (soporta compras Vendors)
                    if hasattr(bo, '_auto_set_destination_on_receipt'):
                        bo._auto_set_destination_on_receipt(first_time_only=False, force=True)

            except Exception as e:
                _logger.debug("Backorder (parcial) ajustes compra/depto falló en %s: %s", bo.name or bo.id, e)

        return backorders

    # =============================
    # Onchange (visual, por si editas en formulario)
    # =============================
    @api.onchange('location_id', 'move_ids_without_package', 'move_ids_without_package.product_id')
    def _onchange_auto_destination(self):
        for picking in self:
            if picking.picking_type_code != 'incoming':
                continue
            # Solo sugerencia visual si aún no se aplicó de forma definitiva
            if not picking.dept_dest_applied:
                dest = picking._compute_department_destination_location()
                if dest and picking.location_dest_id != dest:
                    picking.location_dest_id = dest

    # =============================
    # Sincronía facturas -> OC (tuyo)
    # =============================
    def _sync_invoice_tags_to_purchase(self):
        for picking in self:
            if picking.purchase_id and picking.invoice_order_ids:
                picking.purchase_id.sudo().write({
                    'invoice_tag_ids': [(6, 0, picking.invoice_order_ids.ids)]
                })

    # =============================
    # Núcleo: aplicar destino por Departamento
    # =============================
    def _auto_set_destination_on_receipt(self, first_time_only=True, force=False):
        """Cambia destino a <ROOT_DESDE>/<DEPARTAMENTO>.
        Versión mejorada para manejar correctamente las compras.
        """
        for picking in self:
            if picking.picking_type_code != 'incoming' or picking.state in ('done', 'cancel'):
                continue
            if first_time_only and not force and picking.dept_dest_applied:
                continue

            dest = picking._compute_department_destination_location()
            if not dest:
                _logger.debug("No se encontró destino por departamento para %s", picking.name)
                continue

            if picking.location_dest_id != dest:
                _logger.info("Aplicando destino por depto %s → %s (%s)", 
                            picking.name or picking.id, dest.complete_name, dest.id)

                # Actualizar picking
                picking.location_dest_id = dest.id

                # Actualizar moves abiertos
                picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')).write({
                    'location_dest_id': dest.id
                })

                # Actualizar move lines abiertas
                picking.move_line_ids.filtered(lambda l: getattr(l, 'state', False) not in ('done','cancel')).write({
                    'location_dest_id': dest.id
                })

            if not picking.dept_dest_applied:
                picking.dept_dest_applied = True

    # ---------- Helpers ----------
    def _get_department_text(self):
        """Versión mejorada para obtener el departamento."""
        self.ensure_one()
        
        # 1. Intentar obtener del campo department (si ya está calculado)
        if hasattr(self, 'department') and self.department:
            dept = self.department.strip()
            if dept and not dept.lower().startswith('sin'):
                return dept
        
        # 2. Buscar en los productos de las líneas de movimiento
        PARAM = self.env['barcode.parameter.line']
        PREFIX_LEN = 2
        departments = []
        
        for move in self.move_ids:
            if move.product_id and move.product_id.default_code:
                code = move.product_id.default_code
                prefix = code[:PREFIX_LEN]
                dept = PARAM.search([
                    ('parameter_id.name', '=', 'Departamento'),
                    ('codigo', '=', prefix),
                ], limit=1)
                if dept and dept.nombre:
                    departments.append(dept.nombre.strip())
        
        # 3. Usar el departamento más común
        if departments:
            from collections import Counter
            counter = Counter(departments)
            return counter.most_common(1)[0][0]
        
        return False

    def _get_incoming_root(self):
        """Versión ESPECÍFICA para compras - Corregida"""
        self.ensure_one()
        Location = self.env['stock.location']
        
        _logger.debug("Buscando raíz para picking %s (tipo: %s)", self.name, self.picking_type_code)
        
        # PARA COMPRAS (desde supplier)
        if self.location_id.usage == 'supplier':
            _logger.debug("Es una compra desde supplier")
            
            # OPCIÓN 1: Usar el almacén del tipo de operación
            if self.picking_type_id.warehouse_id:
                warehouse = self.picking_type_id.warehouse_id
                _logger.debug("Almacén encontrado: %s", warehouse.name)
                
                # Buscar la ubicación de stock del almacén
                if warehouse.lot_stock_id:
                    stock_loc = warehouse.lot_stock_id
                    # Subir hasta encontrar la raíz del almacén
                    root = stock_loc
                    while root.location_id:
                        root = root.location_id
                    _logger.debug("Raíz desde almacén: %s", root.complete_name)
                    return root
            
            # OPCIÓN 2: Analizar el nombre del picking para encontrar el almacén
            if self.name:
                # Ejemplo: "TLAJO/ENTRADA/00154" → almacén = "TLAJO"
                warehouse_name = self.name.split('/')[0].strip()
                _logger.debug("Intentando encontrar almacén por nombre: %s", warehouse_name)
                
                # Buscar ubicación raíz con este nombre
                root = Location.search([
                    ('name', '=ilike', warehouse_name),
                    ('location_id', '=', False),
                    ('usage', '=', 'view')  # Las raíces de almacén suelen ser de tipo 'view'
                ], limit=1)
                
                if root:
                    _logger.debug("Raíz encontrada por nombre: %s", root.complete_name)
                    return root
            
            # OPCIÓN 3: Fallback - usar la primera ubicación raíz view
            root = Location.search([
                ('location_id', '=', False),
                ('usage', '=', 'view')
            ], limit=1)
            
            if root:
                _logger.debug("Raíz fallback: %s", root.complete_name)
                return root
        
        # Para traslados internos (mantener lógica original)
        elif self.location_dest_id:
            loc = self.location_dest_id
            while loc.location_id:
                loc = loc.location_id
            return loc
        
        _logger.debug("No se pudo encontrar raíz")
        return False

    def _find_department_location_under(self, root, dept):
        Location = self.env['stock.location']
        # 1) Preferir complete_name "ROOT/DEPTO%"
        dest = Location.search([
            ('id', 'child_of', root.id),
            ('usage', '=', 'internal'),
            ('complete_name', 'ilike', f"{root.name}/{dept}%"),
        ], limit=1)
        if not dest:
            # 2) Segundo intento por name ('CALZADO', 'ACCESORIOS', etc.)
            dest = Location.search([
                ('id', 'child_of', root.id),
                ('usage', '=', 'internal'),
                ('name', 'ilike', dept),
            ], limit=1)
        return dest

    def _compute_department_destination_location(self):
        """Versión MEJORADA con búsqueda más específica"""
        self.ensure_one()
        
        if self.picking_type_code != 'incoming':
            return False

        root = self._get_incoming_root()
        if not root:
            _logger.debug("No se pudo encontrar la raíz para %s", self.name)
            return False

        dept = self._get_department_text()
        if not dept:
            _logger.debug("No se pudo determinar el departamento para %s", self.name)
            return False

        Location = self.env['stock.location']
        
        _logger.debug("Buscando ubicación para depto '%s' bajo raíz '%s'", dept, root.name)
        
        # 1. Buscar directamente: RAÍZ/DEPARTAMENTO
        expected_path = f"{root.name}/{dept}"
        dest = Location.search([
            ('complete_name', '=ilike', expected_path),
            ('usage', '=', 'internal')
        ], limit=1)
        
        if dest:
            _logger.debug("Encontrado por path completo: %s", dest.complete_name)
            return dest
        
        # 2. Buscar hijas de la raíz que coincidan con el departamento
        dest = Location.search([
            ('location_id', '=', root.id),
            ('name', '=ilike', dept),
            ('usage', '=', 'internal')
        ], limit=1)
        
        if dest:
            _logger.debug("Encontrado como hija directa: %s", dest.complete_name)
            return dest
        
        # 3. Buscar en cualquier nivel bajo la raíz
        all_children = Location.search([('id', 'child_of', root.id)])
        for loc in all_children:
            if loc.name.lower() == dept.lower() and loc.usage == 'internal':
                _logger.debug("Encontrado en subniveles: %s", loc.complete_name)
                return loc
        
        _logger.debug("No se encontró ubicación para departamento '%s'", dept)
        return False

    def action_force_destination_correction(self):
        """Acción manual para forzar la corrección del destino"""
        for picking in self:
            if picking.picking_type_code == 'incoming' and picking.state not in ('done', 'cancel'):
                picking._auto_set_destination_on_receipt(first_time_only=False, force=True)
                _logger.info("Destino forzado para %s: %s", picking.name, picking.location_dest_id.complete_name)
        return True

    def action_debug_destination(self):
        """Acción para debuguear el cálculo de destino."""
        for picking in self:
            _logger.info("=== DEBUG DESTINO PARA %s ===", picking.name)
            _logger.info("Tipo: %s (%s)", picking.picking_type_id.name, picking.picking_type_code)
            _logger.info("Ubicación origen: %s (%s)", picking.location_id.complete_name, picking.location_id.usage)
            _logger.info("Ubicación destino actual: %s", picking.location_dest_id.complete_name)
            
            root = picking._get_incoming_root()
            _logger.info("Raíz calculada: %s", root.complete_name if root else "None")
            
            dept = picking._get_department_text()
            _logger.info("Departamento: %s", dept)
            
            dest = picking._compute_department_destination_location()
            _logger.info("Destino calculado: %s", dest.complete_name if dest else "None")
            
            _logger.info("=================================")
        
        return True
    
    def _zero_qty_done_if_purchase_receipt(self, force=False):
        """Pone qty_done=0 en TODAS las líneas de una recepción proveniente de COMPRA.
        - Sólo aplica a pickings incoming con purchase_id
        - No toca pickings done/cancel
        - Si ya se aplicó antes, no vuelve a ejecutar (a menos que force=True)
        """
        for p in self.filtered(lambda r: r.picking_type_code == 'incoming'
                                        and r.purchase_id
                                        and r.state not in ('done', 'cancel')):
            if p.purchase_qty_zeroed and not force:
                continue

            # Si aún no hay líneas, no truena: simplemente lo dejamos para el próximo hook
            if p.move_line_ids:
                # NO pisamos capturas del usuario: esto se usa al crear/confirmar/asignar
                p.move_line_ids.write({'qty_done': 0.0})

            # Marcar que ya inicializamos en 0
            if not p.purchase_qty_zeroed:
                p.purchase_qty_zeroed = True