import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class StockValuationLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    # 1. Campo Almacén
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacén',
        compute='_compute_warehouse_id',
        store=True,
        readonly=True
    )

    # 2. Campo Tipo de Operación
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
            # --- BLINDAJE CONTRA REGISTROS BORRADOS ---
            # Verificamos si existe el movimiento antes de intentar leerlo
            if not layer.stock_move_id or not layer.stock_move_id.exists():
                layer.warehouse_id = False
                continue
            # ------------------------------------------

            # Lógica normal
            wh = False
            # Intentamos leer el picking de forma segura
            if layer.stock_move_id.picking_id:
                wh = layer.stock_move_id.picking_id.picking_type_id.warehouse_id
            
            # Si falla, buscar por ubicación
            if not wh:
                move = layer.stock_move_id
                if layer.quantity >= 0:
                    wh = move.location_dest_id.warehouse_id
                    if not wh and move.location_dest_id.location_id:
                         wh = move.location_dest_id.location_id.warehouse_id
                else:
                    wh = move.location_id.warehouse_id
                    if not wh and move.location_id.location_id:
                         wh = move.location_id.location_id.warehouse_id
            
            layer.warehouse_id = wh

    @api.depends('stock_move_id.picking_id.picking_type_id.code',
                 'stock_move_id.origin_returned_move_id')
    def _compute_movement_type(self):
        for layer in self:
            # --- BLINDAJE CONTRA REGISTROS BORRADOS ---
            if not layer.stock_move_id or not layer.stock_move_id.exists():
                layer.movement_type = 'adjustment'
                continue
            # ------------------------------------------

            move = layer.stock_move_id
            
            # Usamos hasattr para evitar errores si no hay módulo de fabricación
            if hasattr(move, 'production_id') and move.production_id:
                layer.movement_type = 'production'

            elif move.picking_id:
                # Lectura segura del código
                code = False
                if move.picking_id.picking_type_id:
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
        Recálculo forzado de datos históricos.
        """
        _logger.info(">>> INICIANDO RECÁLCULO DE VALORACIÓN (MOOCH) <<<")
        
        records_to_fix = self.search([
            '|', 
            ('warehouse_id', '=', False), 
            ('movement_type', '=', False)
        ])
        
        count = len(records_to_fix)
        if count > 0:
            _logger.info(f">>> Se encontraron {count} registros para actualizar.")
            
            # Iteramos uno por uno en lugar de por lotes para que si uno falla,
            # no detenga a los demás (Try/Except por registro).
            for record in records_to_fix:
                try:
                    record._compute_warehouse_id()
                    record._compute_movement_type()
                except Exception as e:
                    # Si un registro está muy corrupto, lo saltamos y avisamos en el log
                    _logger.warning(f"Error calculando Valuation Layer ID {record.id}: {str(e)}")
                    continue
            
            _logger.info(">>> RECÁLCULO FINALIZADO EXITOSAMENTE <<<")
        else:
            _logger.info(">>> No hay registros pendientes de actualizar. Todo al día. <<<")