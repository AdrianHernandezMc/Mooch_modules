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

    ################# NUEVO MÉTODO: Generar Reporte de Entrega ##############################
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
##################### FIN MÉTODO GENERAR REPORTE ######################################