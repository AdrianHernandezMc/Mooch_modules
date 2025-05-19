from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

class ProductMooch(models.Model):
    _inherit = 'product.template'

    name = fields.Char(
        string="Nombre del Producto",
        compute="_compute_product_name",
        store=True,
        readonly=False
    )
    profit_margin_list = fields.Float(
        string='Porcentaje de Utilidad Precio Lista',
        compute='_compute_profit_margins',
        store=False,
        help="Porcentaje de ganancia sobre el costo"
    )
    profit_margin_cred = fields.Float(
        string='Porcentaje de Utilidad Precio Crédito',
        compute='_compute_profit_margins',
        store=False,
        help="Porcentaje de ganancia sobre el costo"
    )
    list_price = fields.Float(string="Precio de Venta", compute='_compute_prices_list',default=1)
    credit_price = fields.Float(string='Precio Crédito',
                                help='Precio de venta a crédito de Mooch',
                                compute='_compute_prices_cred',
                                default=1)
    partner_name = fields.Many2one('barcode.parameter.line', string='Nombre Proveedor',
                                    help='Nombre del producto del proveedor', domain="[('parameter_id.name', '=', 'Proveedor')]")
    partner_code = fields.Char(string='Codigo Proveedor',
                                    help='Código del producto del proveedor')

    department_id = fields.Many2one(
        'barcode.parameter.line',
        string="Departamento",
        domain="[('parameter_id.name', '=', 'Departamento')]",
        default=lambda self: self._get_default_department(),
    )
    sub_department_id = fields.Many2one(
        'barcode.parameter.line',
        string="Sub Departamento",
        domain="[('parameter_id.name', '=', 'Sub Departamento'),('department_line_ids', 'in', [department_id])] ",
    )
    color_id = fields.Many2one('barcode.parameter.line', string="Color", domain="[('parameter_id.name', '=', 'Color')]")
    type_id = fields.Many2one('barcode.parameter.line', string="Tipo de Producto", domain="[('parameter_id.name', '=', 'Tipo de Producto'), ('department_line_ids', 'in', [department_id])]")
    size_id = fields.Many2one('barcode.parameter.line', string="Talla", domain="[('parameter_id.name', '=', 'Talla'), ('department_line_ids', 'in', [department_id])]")
    consecutive = fields.Char(string="Consecutivo", readonly=True)

    default_code = fields.Char(string="Código Interno", readonly=True)
    barcode = fields.Char(string="Código de Barras", readonly=True)

    show_product_codes = fields.Boolean(
        string="Mostrar Clasificación",
        compute="_compute_show_product_codes",
        store=False
    )
    sale_type = fields.Selection(
        selection=[
            ('sale_type_basic', _('Tipo de Compra Básico')),
            ('sale_type_trend', _('Tipo de Compra Moda')),
            ('sale_type_home', _('Tipo de Compra Hogar')),
            ('sale_type_season', _('Tipo de Compra Temporada'))
        ],
        string='Tipo de Compra',
        help="Seleccione el tipo de compra para usar el porcentaje correspondiente configurado",
        required=True
    )
    unspsc_code_id = fields.Many2one(
        'product.unspsc.code',
        string="Categoría de UNSPSC",
        domain="[('applies_to', '=', 'product')]"
    )

    @api.depends('default_code')
    def _compute_is_locked(self):
        """ Bloquea los campos si el producto ya tiene código asignado """
        for product in self:
            product.is_locked = bool(product.default_code)

    @api.model
    def create(self, vals):
        """ Genera el nombre del producto automáticamente al crear y asegura coherencia de tipos """
        # Establecer departamento predeterminado si no está presente
        if not vals.get('department_id'):
            default_dep = self._get_default_department()
            if default_dep:
                vals['department_id'] = default_dep

        # Verificar que el departamento esté presente
        department_id = vals.get('department_id')
        if not self.env.context.get('install_mode') and not department_id:
            raise ValidationError("El departamento no está definido para este producto.")

        # Establecer valores por defecto obligatorios de Odoo
        vals['available_in_pos'] = True
        vals['detailed_type'] = 'product'  # necesario para que Odoo no falle en validaciones internas
        vals['type'] = 'product'           # asegúrate de que coincida con detailed_type

        # Verificar si se tiene lo necesario para generar código
        if self._is_classification_complete(vals):
            # Generar consecutivo puro por departamento
            consecutive = self._generate_consecutive(department_id)
            vals['consecutive'] = consecutive

            # Generar código interno basado en prefijo + consecutivo
            vals['default_code'] = self._generate_product_code(vals)
            vals['barcode'] = vals['default_code']  # copiar código interno como código de barras

        return super(ProductMooch, self).create(vals)

    def write(self, vals):
        """ Al actualizar un producto existente, genera el nombre y el código si es necesario """
        # Obtener el departamento desde los valores o desde el registro actual
        department_id = vals.get('department_id', self.department_id.id)

        # Verificar si alguno de los campos relacionados con el nombre ha cambiado
        fields_to_check = ['type_id', 'color_id', 'size_id','sub_department_id', 'partner_name', 'partner_code']
        if any(field in vals for field in fields_to_check):
            # Combinar los valores actuales con los nuevos
            new_vals = self._merge_existing_values(vals)
            # No se genera el nombre manualmente, se deja al método computado

        # Verificar si el campo department_id está en los valores actualizados
        if 'department_id' in vals:
            # Combinar los valores existentes con los nuevos
            new_vals = self._merge_existing_values(vals)

            # Verificar si la clasificación está completa y no tiene código aún
            if self._is_classification_complete(new_vals) and not self.default_code:
                # Generar el consecutivo por departamento
                vals['consecutive'] = self._generate_consecutive(department_id)
                # Generar el código de producto
                vals['default_code'] = self._generate_product_code(vals)
                # Asignar el código de barras igual al código interno
                vals['barcode'] = vals['default_code']

        return super(ProductMooch, self).write(vals)


    def _is_classification_complete(self, vals):
        """ Verifica si todos los campos de clasificación están llenos """
        return all(vals.get(field) for field in ['department_id'])

    def _merge_existing_values(self, vals):
        """ Completa los valores faltantes con los datos actuales del producto """
        merged_vals = vals.copy()
        for field in ['department_id']:
            if not merged_vals.get(field):
                merged_vals[field] = getattr(self, field).id
        return merged_vals

    def _generate_consecutive(self, department_id):
        """
        Genera un consecutivo incremental por departamento usando ir.sequence.
        """
        if not department_id:
            raise ValidationError("El departamento no está definido para este producto.")

        # Definir un código de secuencia único para cada departamento
        sequence_code = f'product_mooch.department_{department_id}_sequence'

        # Buscar si ya existe una secuencia para el departamento
        sequence = self.env['ir.sequence'].sudo().search([('code', '=', sequence_code)], limit=1)

        # Crear la secuencia si no existe
        if not sequence:
            sequence = self.env['ir.sequence'].sudo().create({
                'name': f'Secuencia Departamento {department_id}',
                'code': sequence_code,
                'padding': 10,  # Generar solo el número puro de 10 dígitos
                'implementation': 'no_gap',
                'prefix': '',   # Garantizar que no tenga prefijo
                'suffix': '',   # Sin sufijo
                'number_next': 1,
                'number_increment': 1,
            })

        # Obtener el siguiente número puro (sin prefijo)
        new_code = str(sequence.number_next_actual).zfill(10)

        # Incrementar manualmente el número en la secuencia para evitar prefijos
        sequence.sudo().write({'number_next': sequence.number_next_actual + 1})

        # Verificación adicional para asegurar que el código sea solo numérico y de 10 dígitos
        if not new_code.isdigit() or len(new_code) != 10:
            raise ValidationError(f"Consecutivo inválido: {new_code}")

        return new_code

    def _generate_product_code(self, vals):
        """ Genera el código de producto basado en los valores seleccionados """

        def get_code(field_name, default):
            """ Obtiene el código asignado a cada categoría """
            return self.env['barcode.parameter.line'].browse(vals.get(field_name)).codigo if vals.get(field_name) else default

        # Obtener el código del departamento como prefijo de 2 dígitos
        department_code = get_code('department_id', '00')
        consecutive_code = vals.get('consecutive', '0000000000')

        # Verificar si el consecutivo ya contiene el prefijo y corregirlo
        if consecutive_code.startswith(department_code):
            # Eliminar el prefijo redundante para evitar duplicación
            consecutive_code = consecutive_code[len(department_code):]

        # Concatenar el prefijo y el número puro
        return f"{department_code}{consecutive_code}"



    def copy(self, default=None):
        """ Al duplicar un producto, se eliminan los valores que generan el código """
        default = dict(default or {})

        # Se eliminan los valores para que el nuevo producto sea tratado como uno nuevo
        default.update({
            'detailed_type' : 'product',
            'available_in_pos' : True,
            'default_code': False,
            'barcode': False,
            'consecutive': False,
            'color_id': False,
            'type_id': False,
            'size_id': False
        })

        return super(ProductMooch, self).copy(default)


    def unlink(self):
        for product in self:
            if product.default_code or product.barcode:
                raise ValidationError(
                    _("No se puede eliminar un producto que ya tiene un código asignado. "
                      "Puede archivarlo en su lugar.")
                )
        return super(ProductMooch, self).unlink()

    @api.depends()
    def _compute_profit_margins(self):
        param_obj = self.env['ir.config_parameter'].sudo()
        margin_list = float(param_obj.get_param('product_mooch.profit_margin_list', default=0.0))
        margin_cred = float(param_obj.get_param('product_mooch.profit_margin_cred', default=0.0))
        for product in self:
            product.profit_margin_list = margin_list
            product.profit_margin_cred = margin_cred
            
    @api.depends('standard_price', 'profit_margin_list', 'sale_type')
    def _compute_prices_list(self):
        param_obj = self.env['ir.config_parameter'].sudo()
        for product in self:
            
            # Obtener el porcentaje configurado según el tipo de venta
            if product.sale_type == 'sale_type_basic':
                sale_type_value = float(param_obj.get_param('product_mooch.sale_type_basic', default=0.0))
            elif product.sale_type == 'sale_type_trend':
                sale_type_value = float(param_obj.get_param('product_mooch.sale_type_trend', default=0.0))
            elif product.sale_type == 'sale_type_home':
                sale_type_value = float(param_obj.get_param('product_mooch.sale_type_home', default=0.0))
            elif product.sale_type == 'sale_type_season':
                sale_type_value = float(param_obj.get_param('product_mooch.sale_type_season', default=0.0))
            else:
                sale_type_value = 0.0

            # Sumar el porcentaje configurado (por ejemplo, 19% para hogar) con el margen de utilidad contado (por ejemplo, 5%)
            total_percentage = product.profit_margin_list + sale_type_value

            if product.standard_price:
                profit_factor = 1 + (total_percentage / 100)
                product.list_price = round(product.standard_price * profit_factor,0)
            else:
                product.list_price = 0.0

    @api.depends('standard_price', 'profit_margin_cred', 'sale_type')
    def _compute_prices_cred(self):
        """
        Calcula el precio de crédito de la siguiente forma:
        credit_price = standard_price * (1 + ((sale_type_percentage + profit_margin_cred) / 100))
        
        Se suma el % configurado según el tipo de venta al margen de utilidad a crédito.
        """
        param_obj = self.env['ir.config_parameter'].sudo()
        for product in self:
            # Obtener el porcentaje según el tipo de venta
            if product.sale_type == 'sale_type_basic':
                sale_type_value = float(param_obj.get_param('product_mooch.sale_type_basic', default=0.0))
            elif product.sale_type == 'sale_type_trend':
                sale_type_value = float(param_obj.get_param('product_mooch.sale_type_trend', default=0.0))
            elif product.sale_type == 'sale_type_home':
                sale_type_value = float(param_obj.get_param('product_mooch.sale_type_home', default=0.0))
            elif product.sale_type == 'sale_type_season':
                sale_type_value = float(param_obj.get_param('product_mooch.sale_type_season', default=0.0))
            else:
                sale_type_value = 0.0

            # Sumar el porcentaje de tipo de venta con el margen de utilidad de crédito
            total_percentage = sale_type_value + product.profit_margin_cred

            if product.standard_price:
                profit_factor = 1 + (total_percentage / 100)
                product.credit_price = round(product.standard_price * profit_factor,0)
            else:
                product.credit_price = 0.0

    @api.depends('standard_price', 'profit_margin_list', 'sale_type')
    def _compute_final_sale_price(self):
        param_obj = self.env['ir.config_parameter'].sudo()
        for product in self:
            # Obtén el porcentaje configurado según el tipo de venta seleccionado
            if product.sale_type == 'sale_type_basic':
                sale_type_value = float(param_obj.get_param('product_mooch.sale_type_basic', default=0.0))
            elif product.sale_type == 'sale_type_trend':
                sale_type_value = float(param_obj.get_param('product_mooch.sale_type_trend', default=0.0))
            elif product.sale_type == 'sale_type_home':
                sale_type_value = float(param_obj.get_param('product_mooch.sale_type_home', default=0.0))
            elif product.sale_type == 'sale_type_season':
                sale_type_value = float(param_obj.get_param('product_mooch.sale_type_season', default=0.0))
            else:
                sale_type_value = 0.0

            total_percentage = product.profit_margin_list + sale_type_value

            if product.standard_price:
                product.final_sale_price = product.standard_price * (1 + (total_percentage / 100))
            else:
                product.final_sale_price = 0.0

    @api.onchange('type_id')
    def _onchange_type_id_set_unspsc(self):
        for product in self:
            if product.type_id.unspsc_code_id:
                product.unspsc_code_id = product.type_id.unspsc_code_id
            else:
                product.unspsc_code_id = False

    @api.model
    def _get_default_department(self):
        """
        Obtiene el departamento predeterminado del empleado conectado.
        """
        # 1) Obtener el empleado actual
        employee = self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)],
            limit=1
        )
        if not employee or not employee.department_id:
            _logger.warning("🔴 No se encontró el empleado o el departamento para el usuario %s", self.env.uid)
            return False

        # Obtener el nombre del departamento del empleado actual
        dept_name = (employee.department_id.name or '').strip()
        _logger.info("🟢 Departamento detectado del empleado: '%s'", dept_name)

        # 2) Buscar todas las líneas de parámetros relacionadas con "Departamento"
        param_lines = self.env['barcode.parameter.line'].search([
            ('parameter_id.name', '=', 'Departamento')
        ])

        # 3) Búsqueda exacta (case-insensitive) del nombre del departamento
        for line in param_lines:
            if line.nombre and line.nombre.strip().lower() == dept_name.lower():
                _logger.info("🟢 Match exacto: '%s' → '%s'", dept_name, line.nombre)
                return line.id

        # 4) Búsqueda parcial (si el nombre está contenido en el valor)
        for line in param_lines:
            if line.nombre and dept_name.lower() in line.nombre.strip().lower():
                _logger.info("🟢 Match parcial: '%s' in '%s'", dept_name, line.nombre)
                return line.id

        _logger.warning("🔴 No se encontró una línea de parámetro para el departamento '%s'", dept_name)
        return False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'department_id' in fields_list and not res.get('department_id'):
            res['department_id'] = self._get_default_department() or False
        return res

    @api.onchange('department_id')
    def _clear_fields_on_change_department(self):
        self.type_id = False
        self.color_id = False
        self.size_id = False
        return {
            'domain': {
                'type_id': [],
                'color_id': [],
                'size_id': [],
            }
        }

    @api.depends('type_id', 'color_id', 'size_id','sub_department_id' ,'partner_name', 'partner_code')
    def _compute_product_name(self):
        """
        Genera el nombre del producto dinámicamente en función de los campos seleccionados.
        """
        for product in self:
            parts = []

            # Obtener los valores de los campos y añadirlos a la lista solo si existen
            if product.type_id:
                parts.append(product.type_id.nombre)

            if product.color_id:
                parts.append(product.color_id.nombre)

            if product.size_id:
                parts.append(product.size_id.nombre)

            if product.sub_department_id:
                parts.append(product.sub_department_id.nombre)

            if product.partner_name:
                parts.append(product.partner_name.nombre)

            if product.partner_code:
                parts.append(product.partner_code)

            # Generar el nombre concatenando los valores con espacios
            product.name = " ".join(filter(None, parts))

    def action_print_labels(self):
        return self.env.ref('product_mooch.action_report_product_labels').report_action(self)