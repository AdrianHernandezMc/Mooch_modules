from zeep import Client
import requests
from odoo import models, fields, api
from odoo.exceptions import UserError


class SatSync(models.Model):
    _name = 'sat.sync'
    _description = 'Sincronización con el SAT'

    # Campos faltantes que se referencian en la vista
    name = fields.Char(string='Nombre', required=True)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    date_start = fields.Date(string='Fecha inicio', required=True)
    date_end = fields.Date(string='Fecha fin', required=True)
    rfc_emisor = fields.Char(string='RFC Emisor', size=13)
    rfc_receptor = fields.Char(string='RFC Receptor', size=13, required=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('in_progress', 'En progreso'),
        ('done', 'Completado'),
        ('error', 'Error')
    ], string='Estado', default='draft')

    # Campos adicionales útiles
    cfdi_count = fields.Integer(string='CFDIs descargados', compute='_compute_cfdi_count')
    last_sync_date = fields.Datetime(string='Última sincronización')
    error_message = fields.Text(string='Mensaje de error')

    def _compute_cfdi_count(self):
        for record in self:
            record.cfdi_count = self.env['account.move'].search_count([
                ('l10n_mx_edi_cfdi_uuid', '!=', False),
                ('create_date', '>=', record.date_start),
                ('create_date', '<=', record.date_end)
            ])

    def _get_sat_connection(self):
        """Establece conexión con el webservice del SAT"""
        wsdl_url = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl'
        try:
            client = Client(wsdl_url)
            return client
        except Exception as e:
            raise UserError(f"Error al conectar con el SAT: {str(e)}")

    def download_cfdi(self, rfc_emisor=None, rfc_receptor=None, fecha_inicio=None, fecha_fin=None):
        """Descarga CFDIs del SAT"""
        self.ensure_one()
        rfc_emisor = rfc_emisor or self.rfc_emisor
        rfc_receptor = rfc_receptor or self.rfc_receptor
        fecha_inicio = fecha_inicio or self.date_start
        fecha_fin = fecha_fin or self.date_end

        if not all([rfc_receptor, fecha_inicio, fecha_fin]):
            raise UserError("RFC Receptor, Fecha inicio y Fecha fin son campos obligatorios")

        try:
            client = self._get_sat_connection()
            response = client.service.Consulta(
                expresionImpresa=f'Receptor={rfc_receptor} Fecha={fecha_inicio} - {fecha_fin}'
            )
            return self._process_cfdi_response(response)
        except Exception as e:
            self.write({
                'state': 'error',
                'error_message': str(e)
            })
            raise UserError(f"Error al descargar CFDI: {str(e)}")

    def _process_cfdi_response(self, response):
        """Procesa la respuesta del SAT"""
        # Implementa tu lógica para procesar la respuesta XML
        # Esto es un ejemplo básico - deberás adaptarlo a tu estructura real
        cfdis = []
        # ... lógica de procesamiento ...
        return cfdis

    def action_sync_cfdi(self):
        """Acción del botón Sincronizar CFDI"""
        for record in self:
            record.write({'state': 'in_progress'})
            try:
                record.download_cfdi()
                record.write({
                    'state': 'done',
                    'last_sync_date': fields.Datetime.now(),
                    'error_message': False
                })
            except Exception as e:
                record.write({
                    'state': 'error',
                    'error_message': str(e)
                })
                raise