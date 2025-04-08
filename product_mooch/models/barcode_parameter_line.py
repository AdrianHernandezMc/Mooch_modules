from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class BarcodeParameterLine(models.Model):
    _name = 'barcode.parameter.line'
    _description = 'Línea de Configuración para Parámetro de Código de Barras'
    _rec_name = 'nombre'

    parameter_id = fields.Many2one('barcode.parameter', string="Parámetro", required=True, ondelete="cascade")
    nombre = fields.Char(string="Nombre", required=True)
    codigo = fields.Char(string="Código", readonly=True)
    department_line_ids = fields.Many2many(
        'barcode.parameter.line',
        'barcode_parameter_line_department_rel',
        'line_id',
        'department_id',
        string="Departamentos Relacionados",
        domain="[('parameter_id.name', '=', 'Departamento')]",
        help="Requerido para 'Tipo de Producto' y 'Talla'."
    )
    show_department_line = fields.Boolean(
        compute="_compute_show_department_line",
        store=True
    )

    @api.depends('parameter_id.name')
    def _compute_show_department_line(self):
        for rec in self:
            rec.show_department_line = rec.parameter_id.name in ['Talla']

    @api.constrains('parameter_id', 'department_line_ids')
    def _check_department_required(self):
        for rec in self:
            if rec.parameter_id.name in ['Talla'] and not rec.department_line_ids:
                raise ValidationError("El departamento debe de estar Relacionado y es obligatorio para el parametro ''Talla''.")

    @api.model
    def create(self, vals):
        """Genera el código incremental basado en la longitud (digits) del parámetro.
           Si el parámetro es 'Departamento', el incremento será de 10,
           de lo contrario será de 1.
        """
        if not vals.get('parameter_id'):
            return super().create(vals)

        param = self.env['barcode.parameter'].browse(vals['parameter_id'])
        digits = param.digits  # Longitud máxima definida en el padre

        # Obtener la última línea creada para este parámetro, ordenando por código desc
        last_line = self.search([('parameter_id', '=', param.id)], order='codigo desc', limit=1)
        last_code_int = 0
        if last_line and last_line.codigo:
            last_code_int = int(last_line.codigo)

        # Determinar el paso de incremento
        step = 10 if param.name == 'Departamento' else 1
        new_code_int = last_code_int + step

        # Verificar que no exceda el límite
        max_value = (10 ** digits) - 1
        if new_code_int > max_value:
            raise UserError(
                f"Se alcanzó el límite de códigos para el parámetro '{param.name}' "
                f"(máximo {digits} dígitos)."
            )

        # Formatear con ceros a la izquierda
        new_code_str = str(new_code_int).zfill(digits)
        vals['codigo'] = new_code_str

        return super().create(vals)
