from odoo import api, models, fields, _
from odoo.exceptions import UserError
import base64
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
import requests
import logging

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    #################Campos Adrian Muebles##############################
    delivery_contact_name = fields.Char("Nombre de contacto (entrega)")
    delivery_phone = fields.Char("Teléfono (entrega)")
    delivery_address = fields.Char("Dirección (entrega)")
    delivery_notes = fields.Text("Notas de entrega")
    delivery_geo_lat = fields.Float("Latitud (entrega)")
    delivery_geo_lng = fields.Float("Longitud (entrega)")
    delivery_maps_url = fields.Char("URL de Maps")
    #################Fin de campos######################################
    #################Campos nuevos para valdiacion rembolso#############
    refund_order_id = fields.Many2one('pos.order', string='Orden de Reembolso', readonly=True)
    is_return = fields.Boolean(string='Es Reembolso', default=False)
    #################Fin de campos######################################

    @api.model
    def get_order_locations(self, order_ids):
        """
        Retorna para cada order_id un listado de diccionarios con:
            - product_id
            - producto
            - location_id
            - ubicacion_origen
        Utiliza únicamente el ORM de Odoo, sin consultas SQL directas.
        """
        # Carga las órdenes solicitadas
        orders = self.browse(order_ids)
        # Inicializa el resultado con listas vacías
        result = {order.id: [] for order in orders}

        # Mapea origin (nombre de orden) a order_id
        origin_map = {order.name: order.id for order in orders if order.name}
        #raise UserError(f"origin_map {origin_map}")
        #shop/0022;32
        if not origin_map:
            return result

        # Busca movimientos completados cuyas picking.origin coincida con una orden
        moves = self.env['stock.move'].search([
            ('state', '=', 'done'),
            ('picking_id.origin', 'in', list(origin_map.keys())),
        ])
    # Recorre los movimientos y agrupa los datos
        for move in moves:
            origin = move.picking_id.origin
            order_id = origin_map.get(origin)
            if not order_id:
                continue
            result[order_id].append({
                'product_id': move.product_id.id,
                'producto': move.product_id.product_tmpl_id.name,
                'code': move.product_id.product_tmpl_id.default_code,
                'location_id': move.location_id.id,
                'ubicacion_origen': move.location_id.name,
                'origin_id': move.location_dest_id.id,
            })
        return result

##################### NUEVO MÉTODO: Generar Reporte de Entrega ##################################
    @api.model
    def generate_delivery_report(self, report_data):
        """Generar PDF con reporte de entrega"""
        try:
            _logger.info("🖨️ Iniciando generación de reporte de entrega...")

            # Crear PDF en memoria
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)

            # Elementos del reporte
            elements = []
            styles = getSampleStyleSheet()

            # Estilo personalizado para el título
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                alignment=1,  # Centrado
                textColor=colors.HexColor('#2c3e50')
            )

            # Estilo para subtítulos
            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Heading2'],
                fontSize=12,
                spaceAfter=12,
                textColor=colors.HexColor('#34495e')
            )

            # Estilo para contenido
            content_style = ParagraphStyle(
                'CustomContent',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=6
            )

            # Título
            elements.append(Paragraph("📦 REPORTE DE ENTREGA A DOMICILIO", title_style))
            elements.append(Spacer(1, 0.2*inch))

            # Información del pedido
            order_info = [
                ["<b>Número de Pedido:</b>", report_data.get('order_name', 'N/A')],
                ["<b>Fecha y Hora:</b>", report_data.get('order_date', 'N/A')],
                ["<b>Cliente:</b>", report_data.get('partner_name', 'Cliente no especificado')],
                ["<b>Teléfono:</b>", report_data.get('partner_phone', 'N/A')],
            ]

            order_table = Table(order_info, colWidths=[2*inch, 4*inch])
            order_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
            ]))

            elements.append(order_table)
            elements.append(Spacer(1, 0.2*inch))

            # Información de entrega
            delivery_data = report_data.get('delivery_data', {})
            delivery_info = [
                ["<b>INFORMACIÓN DE ENTREGA</b>", ""],
                ["Contacto:", delivery_data.get('contact_name', 'N/A')],
                ["Teléfono de entrega:", delivery_data.get('phone', 'N/A')],
                ["Dirección:", delivery_data.get('address', 'N/A')],
                ["Notas:", delivery_data.get('notes', 'Sin notas')],
            ]

            delivery_table = Table(delivery_info, colWidths=[2*inch, 4*inch])
            delivery_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
            ]))

            elements.append(delivery_table)
            elements.append(Spacer(1, 0.2*inch))

            # Coordenadas y mapa
            if delivery_data.get('lat') and delivery_data.get('lng'):
                coords_info = [
                    ["<b>UBICACIÓN GPS</b>", ""],
                    ["Latitud:", str(delivery_data.get('lat', 'N/A'))],
                    ["Longitud:", str(delivery_data.get('lng', 'N/A'))],
                    ["Google Maps:", delivery_data.get('maps_url', 'N/A')],
                ]

                coords_table = Table(coords_info, colWidths=[1.5*inch, 4.5*inch])
                coords_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 11),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#d5f4e6')),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                ]))

                elements.append(coords_table)
                elements.append(Spacer(1, 0.2*inch))

                # Generar código QR con la ubicación
                try:
                    maps_url = delivery_data.get('maps_url', '')
                    if maps_url:
                        qr_code = qr.QrCodeWidget(maps_url)
                        bounds = qr_code.getBounds()
                        width = bounds[2] - bounds[0]
                        height = bounds[3] - bounds[1]
                        drawing = Drawing(100, 100, transform=[100./width,0,0,100./height,0,0])
                        drawing.add(qr_code)
                        elements.append(Spacer(1, 0.1*inch))
                        elements.append(Paragraph("<b>Escanea para ver en Google Maps:</b>", content_style))
                        elements.append(drawing)
                except Exception as qr_error:
                    _logger.warning(f"No se pudo generar QR: {qr_error}")

            # Instrucciones de entrega
            instructions = [
                "• Verificar identificación del destinatario",
                "• Confirmar dirección antes de entregar", 
                "• Tomar foto como evidencia si es necesario",
                "• Reportar cualquier incidencia al supervisor",
                "• Horario preferente: 9:00 AM - 6:00 PM"
            ]

            elements.append(Spacer(1, 0.2*inch))
            elements.append(Paragraph("<b>INSTRUCCIONES DE ENTREGA:</b>", subtitle_style))
            for instruction in instructions:
                elements.append(Paragraph(f"✓ {instruction}", content_style))

            # Pie de página
            elements.append(Spacer(1, 0.3*inch))
            company_name = report_data.get('company', {}).get('name', 'Mooch')
            pos_config_name = report_data.get('pos_config', {}).get('name', 'POS')
            elements.append(Paragraph(
                f"<i>Generado automáticamente por {company_name} - {pos_config_name}</i>", 
                ParagraphStyle('Footer', parent=styles['Italic'], fontSize=8, textColor=colors.gray)
            ))

            # Generar PDF
            doc.build(elements)

            # Obtener bytes del PDF
            pdf_bytes = buffer.getvalue()
            buffer.close()

            # Convertir a base64 para enviar al frontend
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

            _logger.info("✅ Reporte de entrega generado exitosamente")
            return pdf_base64

        except Exception as e:
            _logger.error(f"❌ Error generando reporte de entrega: {str(e)}")
            return None
##################### FIN MÉTODOS GENERAR REPORTE ################################################

##################### MÉTODOS MODIFICACION REMBOLSO POS ##########################################
    def _create_order_picking(self):
        """Método mejorado para diagnóstico y manejo de devoluciones"""
        _logger.info("🎯 [DIAGNÓSTICO] _create_order_picking llamado")
        _logger.info("🎯 [DIAGNÓSTICO] Orden: %s", self.name)
        
        # ✅ DETECCIÓN ROBUSTA - No depender solo de is_return
        order_name_upper = (self.name or '').upper()
        is_refund = any([
            getattr(self, 'is_return', False),
            'REEMBOLSO' in order_name_upper,
            'DEVOLUCIÓN' in order_name_upper, 
            'REFUND' in order_name_upper,
            self.amount_total < 0,  # Total negativo
            any('REEMBOLSO' in (line.name or '').upper() for line in self.lines)
        ])
        
        _logger.info("🎯 [DIAGNÓSTICO] is_return field: %s", getattr(self, 'is_return', 'No existe'))
        _logger.info("🎯 [DIAGNÓSTICO] Nombre orden: %s", self.name)
        _logger.info("🎯 [DIAGNÓSTICO] Total orden: %s", self.amount_total)
        _logger.info("🎯 [DIAGNÓSTICO] Detectado como devolución: %s", is_refund)
        _logger.info("🎯 [DIAGNÓSTICO] Líneas: %s", len(self.lines))
        
        for line in self.lines:
            product = line.product_id
            department = product.product_tmpl_id.department_id
            _logger.info("🎯 [DIAGNÓSTICO] Producto: %s, Departamento: %s", 
                        product.name, department.nombre if department else "Sin departamento")
        
        # ✅ EJECUTAR LÓGICA PERSONALIZADA SI ES DEVOLUCIÓN
        if is_refund:
            _logger.info("🎯 [DIAGNÓSTICO] 🚀 Ejecutando lógica personalizada para DEVOLUCIÓN")
            return self._create_custom_return_picking()
        else:
            _logger.info("🎯 [DIAGNÓSTICO] Ejecutando lógica estándar de Odoo")
            return super()._create_order_picking()

    def _create_custom_return_picking(self):
        """
        Crea picking de reembolso con ubicaciones personalizadas por departamento
        UN PICKING POR DEPARTAMENTO (ubicación destino)
        """
        _logger.info("🎯 [ODOO-CUSTOM] Creando picking personalizado para reembolso POS")
        
        try:
            # ✅ OBTENER EL ALMACÉN CORRECTO
            warehouse = self._get_correct_warehouse()
            if not warehouse:
                _logger.error("🎯 [ODOO-CUSTOM] No se pudo determinar el almacén para la orden")
                raise UserError("No se pudo determinar el almacén para procesar el reembolso")

            _logger.info(f"🎯 [ODOO-CUSTOM] Usando almacén: {warehouse.name}")

            # 1. BÚSQUEDA ROBUSTA DE TIPO DE OPERACIÓN
            picking_type = self._find_picking_type_for_returns(warehouse)
            if not picking_type:
                _logger.error("🎯 [ODOO-CUSTOM] No se pudo encontrar ningún tipo de operación válido")
                raise UserError("No se encontró un tipo de operación configurado para reembolsos")

            _logger.info(f"🎯 [ODOO-CUSTOM] Usando tipo de operación: {picking_type.name}")

            # 2. OBTENER UBICACIÓN ORIGEN (Clientes)
            location_id = self.env.ref('stock.stock_location_customers')
            if not location_id:
                _logger.error("🎯 [ODOO-CUSTOM] No se pudo encontrar la ubicación de clientes")
                raise UserError("No se pudo encontrar la ubicación de clientes")

            _logger.info(f"🎯 [ODOO-CUSTOM] Ubicación origen (Clientes): {location_id.complete_name}")

            # 3. ✅ AGRUPAR LÍNEAS POR DEPARTAMENTO (ubicación destino)
            lines_by_department = {}
            
            for line in self.lines:
                product = line.product_id
                _logger.info(f"🎯 [ODOO-CUSTOM] Procesando línea: {product.name}")
                
                # ✅ OBTENER EL DEPARTAMENTO DESDE EL PRODUCT TEMPLATE
                product_template = product.product_tmpl_id
                department = product_template.department_id
                
                _logger.info(f"🎯 [ODOO-CUSTOM] Departamento del producto: {department.nombre if department else 'Sin departamento'}")
                
                # Determinar la ubicación destino específica
                custom_location_dest_id = self._get_custom_destination_location(
                    warehouse.lot_stock_id,
                    department,
                    warehouse
                )

                _logger.info(f"🎯 [ODOO-CUSTOM] Ubicación destino: {custom_location_dest_id.complete_name}")

                # Agrupar por ubicación destino
                location_key = custom_location_dest_id.id
                if location_key not in lines_by_department:
                    lines_by_department[location_key] = {
                        'location_dest': custom_location_dest_id,
                        'lines': []
                    }
                
                lines_by_department[location_key]['lines'].append((0, 0, {
                    'name': f"REEMBOLSO POS: {product.name}",
                    'product_id': product.id,
                    'product_uom_qty': abs(line.qty),
                    'product_uom': product.uom_id.id,
                    'location_id': location_id.id,
                    'location_dest_id': custom_location_dest_id.id,
                }))

            _logger.info(f"🎯 [ODOO-CUSTOM] Se crearán {len(lines_by_department)} picking(s) por departamento")

            # 4. ✅ CREAR UN PICKING POR DEPARTAMENTO (ubicación destino)
            created_pickings = []
            
            for location_key, department_data in lines_by_department.items():
                custom_location_dest_id = department_data['location_dest']
                move_lines = department_data['lines']
                
                _logger.info(f"🎯 [ODOO-CUSTOM] Creando picking para ubicación: {custom_location_dest_id.complete_name}")
                _logger.info(f"🎯 [ODOO-CUSTOM] Líneas en este picking: {len(move_lines)}")

                picking_vals = {
                    'origin': self.name,
                    'partner_id': self.partner_id.id or False,
                    'user_id': False,
                    'date_deadline': fields.Datetime.now(),
                    'picking_type_id': picking_type.id,
                    'company_id': self.company_id.id,
                    'move_ids_without_package': move_lines,
                    'location_id': location_id.id,
                    'location_dest_id': custom_location_dest_id.id,
                    'note': f"Reembolso generado automáticamente desde POS. Orden: {self.name}. Departamento: {custom_location_dest_id.name}",
                    # ✅ VINCULAR CON LA ORDEN POS
                    'pos_order_id': self.id,
                }

                picking = self.env['stock.picking'].create(picking_vals)
                _logger.info(f"🎯 [ODOO-CUSTOM] Picking Devoluciones POS creado: {picking.name} para {custom_location_dest_id.complete_name}")

                # 5. Confirmar y validar cada picking
                picking.action_confirm()
                picking.action_assign()

                if picking.state == 'assigned':
                    picking.button_validate()
                    _logger.info(f"🎯 [ODOO-CUSTOM] Picking POS validado: {picking.name}")
                else:
                    _logger.warning(f"🎯 [ODOO-CUSTOM] Picking POS no pudo ser validado automáticamente: {picking.state}")

                created_pickings.append(picking)

            _logger.info(f"🎯 [ODOO-CUSTOM] Se crearon {len(created_pickings)} picking(s) exitosamente")
            
            # Retornar el primer picking creado (para compatibilidad con el flujo existente)
            return created_pickings[0] if created_pickings else False

        except Exception as e:
            _logger.error(f"🎯 [ODOO-CUSTOM] Error crítico creando picking de reembolso: {str(e)}")
            return False

    def _find_picking_type_for_returns(self, warehouse):
        """
        Búsqueda robusta de tipos de operación para reembolsos
        """
        _logger.info(f"🎯 [PICKING-TYPE] Buscando tipo de operación para almacén: {warehouse.name}")
        
        # Estrategia 1: Buscar tipo específico para reembolsos POS
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'pos_returns'),
            ('warehouse_id', '=', warehouse.id),
        ], limit=1)
        
        if picking_type:
            _logger.info(f"🎯 [PICKING-TYPE] Encontrado tipo 'pos_returns': {picking_type.name}")
            return picking_type

        # Estrategia 2: Buscar tipo de entrada en el almacén específico
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('warehouse_id', '=', warehouse.id),
        ], limit=1)
        
        if picking_type:
            _logger.info(f"🎯 [PICKING-TYPE] Encontrado tipo 'incoming' en almacén: {picking_type.name}")
            return picking_type

        # Estrategia 3: Buscar tipo de entrada en cualquier almacén de la compañía
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('warehouse_id.company_id', '=', self.company_id.id),
        ], limit=1)
        
        if picking_type:
            _logger.info(f"🎯 [PICKING-TYPE] Encontrado tipo 'incoming' en compañía: {picking_type.name}")
            return picking_type

        # Estrategia 4: Buscar CUALQUIER tipo de operación de entrada
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
        ], limit=1)
        
        if picking_type:
            _logger.info(f"🎯 [PICKING-TYPE] Encontrado tipo 'incoming' global: {picking_type.name}")
            return picking_type

        # Estrategia 5: Último recurso - cualquier tipo de operación interno
        picking_type = self.env['stock.picking.type'].search([
            ('code', 'in', ['internal', 'incoming', 'outgoing']),
        ], limit=1)
        
        if picking_type:
            _logger.warning(f"🎯 [PICKING-TYPE] Usando tipo de operación genérico: {picking_type.name}")
            return picking_type

        _logger.error("🎯 [PICKING-TYPE] No se encontró ningún tipo de operación")
        return False

    def _get_correct_warehouse(self):
        """
        Obtiene el almacén correcto basado en la configuración del POS
        """
        try:
            # Opción 1: Usar el almacén de la configuración del POS
            if self.config_id and self.config_id.warehouse_id:
                _logger.info(f"🎯 [WAREHOUSE] Usando almacén de la configuración POS: {self.config_id.warehouse_id.name}")
                return self.config_id.warehouse_id
            
            # Opción 2: Buscar por el nombre de la orden (ej: GRAL/TLAJO/01/...)
            order_name = self.name or ""
            warehouse_mapping = {
                'TLAJO': 'Tlajomulco',  # Nombre exacto del almacén
                'IXTLA': 'Ixtlahuacán', 
                'TERRA': 'Terranova',
                'ALMAC': 'Almacen'
            }
            
            for key, warehouse_name in warehouse_mapping.items():
                if key in order_name.upper():
                    warehouse = self.env['stock.warehouse'].search([
                        ('name', '=', warehouse_name),  # Búsqueda exacta
                        ('company_id', '=', self.company_id.id)
                    ], limit=1)
                    if warehouse:
                        _logger.info(f"🎯 [WAREHOUSE] Encontrado por nombre de orden: {warehouse.name}")
                        return warehouse
            
            # Opción 3: Usar el almacén por defecto de la compañía
            default_warehouse = self.env['stock.warehouse'].search([
                ('company_id', '=', self.company_id.id)
            ], limit=1)
            
            if default_warehouse:
                _logger.info(f"🎯 [WAREHOUSE] Usando almacén por defecto: {default_warehouse.name}")
                return default_warehouse
                
            _logger.error("🎯 [WAREHOUSE] No se encontró ningún almacén")
            return False
            
        except Exception as e:
            _logger.error(f"🎯 [WAREHOUSE] Error buscando almacén: {str(e)}")
            return False

    def _get_original_sale_location(self):
        """
        Busca la ubicación de destino de la venta original
        para usarla como ubicación origen del reembolso
        """
        try:
            # Buscar por el nombre de la orden original (quitando 'REEMBOLSO')
            original_order_name = self.name.replace('REEMBOLSO', '').strip()
            
            # Buscar movimientos de la orden original
            original_moves = self.env['stock.move'].search([
                ('picking_id.origin', 'ilike', original_order_name),
                ('state', '=', 'done')
            ], order='id desc', limit=10)
            
            for move in original_moves:
                if move.location_dest_id:
                    original_location = move.location_dest_id
                    _logger.info(f"🎯 [ORIGINAL] Ubicación destino original encontrada: {original_location.complete_name}")
                    return original_location
            
            _logger.warning("🎯 [ORIGINAL] No se encontró movimiento original con ubicación destino")
            return False
            
        except Exception as e:
            _logger.error(f"🎯 [ORIGINAL] Error buscando ubicación original: {str(e)}")
            return False

    def _get_custom_destination_location(self, default_location, department, warehouse=False):
        """
        Determine the custom destination location based on product department
        for return pickings, using ONLY EXISTING locations.
        """
        _logger.info(f"🎯 [LOCATION] Buscando ubicación personalizada para departamento: {department.nombre if department else 'Sin departamento'}")
        
        try:
            # Si no hay departamento, retornar ubicación por defecto
            if not department:
                _logger.info(f"🎯 [LOCATION] Sin departamento, usando ubicación por defecto: {default_location.complete_name}")
                return default_location
            
            # Obtener el nombre REAL del departamento desde barcode.parameter.line
            dept_name = department.nombre
            if not dept_name:
                _logger.warning("🎯 [LOCATION] El departamento no tiene nombre, usando ubicación por defecto")
                return default_location

            _logger.info(f"🎯 [LOCATION] Buscando ubicación existente para departamento: {dept_name}")
            
            # ✅ SOLO BUSCAR UBICACIONES EXISTENTES - NO CREAR NUEVAS
            custom_location = self._find_existing_department_location(dept_name, warehouse)
            
            if custom_location:
                _logger.info(f"🎯 [LOCATION] Ubicación encontrada para {dept_name}: {custom_location.complete_name}")
                return custom_location
            else:
                _logger.warning(f"🎯 [LOCATION] No se encontró ubicación existente para departamento: {dept_name}")
                # ✅ NO CREAR UBICACIÓN - Usar ubicación por defecto del almacén
                _logger.info(f"🎯 [LOCATION] Usando ubicación por defecto del almacén: {default_location.complete_name}")
                return default_location
            
        except Exception as e:
            _logger.error(f"🎯 [LOCATION] Error buscando ubicación personalizada: {str(e)}")
            if default_location:
                _logger.info(f"🎯 [LOCATION] Usando ubicación por defecto por error: {default_location.complete_name}")
                return default_location
            else:
                return self._get_fallback_location(warehouse)

    def _find_existing_department_location(self, dept_name, warehouse):
        """
        Busca SOLO ubicaciones EXISTENTES por nombre de departamento
        con estructura ALMACÉN/DEPARTAMENTO. NO crea nuevas ubicaciones.
        """
        _logger.info(f"🎯 [LOCATION-SEARCH] Buscando ubicación EXISTENTE: {dept_name} en almacén {warehouse.name if warehouse else 'N/A'}")
        
        # Estrategia 1: Buscar en el almacén específico con estructura ALMACÉN/DEPARTAMENTO
        if warehouse:
            # Buscar ubicación que sea hija directa del almacén y tenga el nombre del departamento
            location = self.env['stock.location'].search([
                ('name', '=ilike', dept_name),
                ('location_id', '=', warehouse.lot_stock_id.id),
                ('usage', '=', 'internal'),
            ], limit=1)
            
            if location:
                _logger.info(f"🎯 [LOCATION-SEARCH] Encontrada en almacén específico: {location.complete_name}")
                return location
            
            # Posibilidades de rutas
            possible_paths = [
                f"{warehouse.name}/{dept_name}",
                f"{warehouse.lot_stock_id.name}/{dept_name}",
                f"TLAJO/{dept_name}",  # Nombre específico para Tlajomulco
                f"IXTLA/{dept_name}",  # Nombre específico para Ixtlahuacán
                f"TERRA/{dept_name}",  # Nombre específico para Terranova
                f"ALMAC/{dept_name}",  # Nombre específico para Almacen
            ]
            
            for path in possible_paths:
                location = self.env['stock.location'].search([
                    ('complete_name', '=ilike', path),
                    ('usage', '=', 'internal'),
                ], limit=1)
                
                if location:
                    _logger.info(f"🎯 [LOCATION-SEARCH] Encontrada por path: {location.complete_name}")
                    return location
        
        # Buscar ubicaciones que contengan el nombre del departamento Y estén en el almacén correcto
        if warehouse:
            all_dept_locations = self.env['stock.location'].search([
                ('name', '=ilike', dept_name),
                ('usage', '=', 'internal'),
                ('company_id', '=', self.company_id.id),
            ])
            
            # Filtrar las que pertenecen al almacén correcto verificando la jerarquía
            for location in all_dept_locations:
                current_loc = location
                found_in_warehouse = False
                
                # Recorrer la jerarquía hacia arriba para verificar si está en el almacén correcto
                while current_loc.location_id:
                    if current_loc == warehouse.lot_stock_id:
                        found_in_warehouse = True
                        break
                    current_loc = current_loc.location_id
                
                if found_in_warehouse:
                    _logger.info(f"🎯 [LOCATION-SEARCH] Encontrada en jerarquía del almacén: {location.complete_name}")
                    return location
        
        # Buscar por nombre exacto en cualquier lugar (fallback)
        location = self.env['stock.location'].search([
            ('name', '=', dept_name),
            ('usage', '=', 'internal'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        
        if location:
            _logger.info(f"🎯 [LOCATION-SEARCH] Encontrada por nombre exacto: {location.complete_name}")
            return location
        
        _logger.warning(f"🎯 [LOCATION-SEARCH] No se encontró ubicación existente para {dept_name}")
        return False

    def _create_department_location_with_structure(self, dept_name, warehouse):
        """
        Crea automáticamente una ubicación para un departamento con estructura ALMACÉN/DEPARTAMENTO
        """
        try:
            # Usar la ubicación de stock del almacén como padre
            if warehouse and warehouse.lot_stock_id:
                parent_location = warehouse.lot_stock_id
                _logger.info(f"🎯 [LOCATION-CREATE] Creando ubicación {dept_name} bajo {parent_location.complete_name}")
            else:
                parent_location = self.env['stock.location'].search([
                    ('usage', '=', 'internal'),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)
                if not parent_location:
                    _logger.error("🎯 [LOCATION-CREATE] No se encontró ubicación padre para crear departamento")
                    return False
            
            existing_location = self.env['stock.location'].search([
                ('name', '=', dept_name),
                ('location_id', '=', parent_location.id),
            ], limit=1)
            
            if existing_location:
                _logger.info(f"🎯 [LOCATION-CREATE] Ubicación ya existe: {existing_location.complete_name}")
                return existing_location
            
            location_vals = {
                'name': dept_name,
                'location_id': parent_location.id,
                'usage': 'internal',
                'company_id': self.company_id.id,
            }
            
            new_location = self.env['stock.location'].create(location_vals)
            _logger.info(f"🎯 [LOCATION-CREATE] Ubicación creada: {new_location.complete_name}")
            return new_location
            
        except Exception as e:
            _logger.error(f"🎯 [LOCATION-CREATE] Error creando ubicación {dept_name}: {str(e)}")
            return False

    def _get_fallback_location(self, warehouse):
        """
        Obtiene una ubicación de fallback segura
        """
        if warehouse and warehouse.lot_stock_id:
            return warehouse.lot_stock_id
        
        any_location = self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        
        if any_location:
            return any_location
        
        raise UserError("No hay ubicaciones internas configuradas en el sistema. Contacte al administrador.")
##################### FIN MÉTODOS MODIFICACION REMBOLSO POS ######################################