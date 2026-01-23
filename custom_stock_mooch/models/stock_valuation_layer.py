import logging
from odoo import models, fields, api


_logger = logging.getLogger(__name__)


class StockValuationLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacén',
        compute='_compute_warehouse_id',
        store=True,
        readonly=True
    )

    movement_type = fields.Selection([
        ('sale', 'Venta / Salida'),
        ('purchase', 'Compra / Entrada'),
        ('transfer', 'Traslado Interno'),
        ('production', 'Fabricación'),
        ('adjustment', 'Ajuste / Otro'),
        ('return', 'Devolución')
    ], string='Tipo Operación', compute='_compute_movement_type', store=True)

    @api.depends('stock_move_id.picking_id.picking_type_id.warehouse_id', 
                 'stock_move_id.location_id', 
                 'stock_move_id.location_dest_id')
    def _compute_warehouse_id(self):
        for layer in self:
            # 1. Intento principal: Buscar por el tipo de operación (Ventas/Compras/POS)
            wh = layer.stock_move_id.picking_id.picking_type_id.warehouse_id
            
            # 2. Si falla (ej. Ajuste de Inventario), buscar por la ubicación
            if not wh and layer.stock_move_id:
                move = layer.stock_move_id
                # Si entra stock (positivo) o es interno, miramos el destino
                if layer.quantity >= 0:
                    wh = move.location_dest_id.warehouse_id
                    # A veces el warehouse_id está en la ubicación padre (View location)
                    if not wh:
                         wh = move.location_dest_id.location_id.warehouse_id
                # Si sale stock (negativo), miramos el origen
                else:
                    wh = move.location_id.warehouse_id
                    if not wh:
                         wh = move.location_id.location_id.warehouse_id
            
            layer.warehouse_id = wh

    @api.depends('stock_move_id.picking_id.picking_type_id.code',
                 'stock_move_id.origin_returned_move_id')
    def _compute_movement_type(self):
        for layer in self:
            # --- BLINDAJE DE SEGURIDAD ---
            if not layer.stock_move_id or not layer.stock_move_id.exists():
                layer.movement_type = 'adjustment' # Asumimos ajuste si no hay movimiento
                continue
            # -----------------------------

            move = layer.stock_move_id
            
            if hasattr(move, 'production_id') and move.production_id:
                layer.movement_type = 'production'

            elif move.picking_id:
                code = move.picking_id.picking_type_id.code 
                
                if move.origin_returned_move_id:
                    layer.movement_type = 'return'
                elif code == 'outgoing':
                    layer.movement_type = 'sale'
                elif code == 'incoming':
                    layer.movement_type = 'purchase'
                elif code == 'internal':
                    layer.movement_type = 'transfer'
                else:
                    layer.movement_type = 'adjustment'
            else:
                layer.movement_type = 'adjustment'

    @api.model
    def action_recalculate_mooch_fields(self):
        """
        Busca registros antiguos sin almacén o tipo y fuerza el cálculo.
        Se ejecuta automáticamente desde el XML al actualizar el módulo.
        """
        _logger.info(">>> INICIANDO RECÁLCULO DE VALORACIÓN (MOOCH) <<<")
        
        # Buscamos registros donde warehouse_id O movement_type estén vacíos
        # El operador '|' significa OR en la notación polaca de Odoo
        records_to_fix = self.search([
            '|', 
            ('warehouse_id', '=', False), 
            ('movement_type', '=', False)
        ])
        
        count = len(records_to_fix)
        if count > 0:
            _logger.info(f">>> Se encontraron {count} registros para actualizar.")
            
            # Ejecutamos los computes manualmente sobre esos registros
            records_to_fix._compute_warehouse_id()
            records_to_fix._compute_movement_type()
            
            _logger.info(">>> RECÁLCULO FINALIZADO EXITOSAMENTE <<<")
        else:
            _logger.info(">>> No hay registros pendientes de actualizar. Todo al día. <<<")