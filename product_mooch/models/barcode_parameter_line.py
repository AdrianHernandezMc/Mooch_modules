from odoo import models, fields, api
from odoo.exceptions import UserError

class BarcodeParameterLine(models.Model):
    _name = 'barcode.parameter.line'
    _description = 'Línea de Configuración para Parámetro de Código de Barras'
    _rec_name = 'nombre'
    _order = 'orden_departamento_id, codigo'

    name = fields.Char(string='Nombre')
    parameter_id = fields.Many2one('barcode.parameter', string="Parámetro", required=True, ondelete="cascade")
    nombre = fields.Char(string="Nombre", required=True, store=True)
    codigo = fields.Char(string="Código", readonly=True, store=True)
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
    unspsc_code_id = fields.Many2one(
        'product.unspsc.code',
        string='Código UNSPSC',
        help='Código estándar UNSPSC asociado a esta línea.'
    )
    orden_departamento_id = fields.Many2one(
        'barcode.parameter.line',
        string='Departamento Principal para Orden',
        domain="[('parameter_id.name', '=', 'Departamento')]",
        compute='_compute_orden_departamento',
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
                raise UserError("El departamento debe de estar Relacionado y es obligatorio para el parámetro 'Talla'.")

    @api.model
    def create(self, vals):
        """
        Genera el código incremental basado en la longitud (digits) del parámetro.
        Si el parámetro es 'Departamento', el incremento será de 10,
        de lo contrario será de 1.

        Para los parámetros 'Tipo de Producto' y 'Talla', si se envía 
        información en department_line_ids, se filtra la búsqueda del último código por
        esos departamentos.
        """
        if not vals.get('parameter_id'):
            return super().create(vals)

        param = self.env['barcode.parameter'].browse(vals['parameter_id'])
        digits = param.digits  # Longitud máxima definida en el padre

        # Definir dominio base: todos los registros para este parámetro.
        domain = [('parameter_id', '=', param.id)]

        # Para "Tipo de Producto" y "Talla", si se envía información en department_line_ids, filtrar por ellos
        if param.name in ['Tipo de Producto', 'Talla']:
            dept_ids = []
            if vals.get('department_line_ids'):
                # Los comandos en Many2many pueden venir en distintos formatos: 
                # Por ejemplo, (6, 0, [ids]) o (4, id).
                for command in vals.get('department_line_ids'):
                    # Si es un comando de tipo (6, 0, [ids]), extraer la lista de IDs
                    if isinstance(command, (list, tuple)) and command[0] == 6:
                        dept_ids.extend(command[2])
                    # Si es un comando de tipo (4, id), extraer el id
                    elif isinstance(command, (list, tuple)) and command[0] in (4, 5) and command[1]:
                        dept_ids.append(command[1])
                    elif isinstance(command, int):
                        dept_ids.append(command)
            if dept_ids:
                domain.append(('department_line_ids', 'in', dept_ids))

        # Buscar el último registro para este parámetro (y, si aplica, filtrado por los departamentos)
        last_line = self.search(domain, order='codigo desc', limit=1)
        last_code_int = 0
        if last_line and last_line.codigo:
            try:
                last_code_int = int(last_line.codigo)
            except ValueError:
                last_code_int = 0

        # Paso de incremento: de 10 si el parámetro es 'Departamento', sino 1.
        step = 10 if param.name == 'Departamento' else 1
        new_code_int = last_code_int + step

        # Verificar que no exceda el límite
        max_value = (10 ** digits) - 1
        if new_code_int > max_value:
            raise UserError(
                f"Se alcanzó el límite de códigos para el parámetro '{param.name}' (máximo {digits} dígitos)."
            )

        new_code_str = str(new_code_int).zfill(digits)
        vals['codigo'] = new_code_str

        return super().create(vals)
    
    @api.depends('department_line_ids')
    def _compute_orden_departamento(self):
        for rec in self:
            rec.orden_departamento_id = rec.department_line_ids[:1].id if rec.department_line_ids else False
