from odoo import models, fields, api
from odoo.exceptions import UserError

class BarcodeParameter(models.Model):
    _name = 'barcode.parameter'
    _description = 'Parámetro de Nomenclatura de Código de Barras'

    name = fields.Char(string="Parámetro", required=True, store=True)
    digits = fields.Integer(string="Longitud Máxima", required=True, default=2, store=True)
    line_ids = fields.One2many('barcode.parameter.line', 'parameter_id', string="Líneas de Configuración",store=True)

    @api.model
    def create(self, vals):
        # Allow creation if it's an import or module installation
        if not (self.env.context.get('from_import') or 
                self.env.context.get('import_file') or 
                self.env.context.get('install_mode')):  # Allow during module install
            raise UserError("No se permite la creación manual de registros. Utilice la opción de importación.")
        return super(BarcodeParameter, self).create(vals)