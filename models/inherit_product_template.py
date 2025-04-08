from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class ProductMooch(models.Model):
    _inherit = 'product.template'

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
    credit_price = fields.Integer(string='Precio Crédito',
                                  help='Precio de venta a crédito de Mooch',
                                  compute='_compute_prices_cred',
                                  default=1)
    partner_reference = fields.Char(string='Referencia Proveedor',
                                    help='Código del producto del proveedor')

    department_id = fields.Many2one('barcode.parameter.line', string="Departamento", domain="[('parameter_id.name', '=', 'Departamento')]")
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

    @api.depends('default_code')
    def _compute_is_locked(self):
        """ Bloquea los campos si el producto ya tiene código asignado """
        for product in self:
            product.is_locked = bool(product.default_code)

    @api.model
    def create(self, vals):
        """ Genera el código automáticamente solo si todos los campos están completos """
        vals['available_in_pos'] = True
        vals['detailed_type'] = 'product'
        if self._is_classification_complete(vals):
            vals['consecutive'] = self._generate_consecutive()
            vals['default_code'] = self._generate_product_code(vals)
            vals['barcode'] = vals['default_code']
        return super(ProductMooch, self).create(vals)

    def write(self, vals):
        """ Al actualizar un producto existente, genera código si todos los campos están completos """
        if any(field in vals for field in ['department_id', 'color_id', 'type_id', 'size_id']):
            new_vals = self._merge_existing_values(vals)
            if self._is_classification_complete(new_vals) and not self.default_code:
                vals['consecutive'] = self._generate_consecutive()
                vals['default_code'] = self._generate_product_code(vals)
                vals['barcode'] = vals['default_code']
        return super(ProductMooch, self).write(vals)

    def _is_classification_complete(self, vals):
        """ Verifica si todos los campos de clasificación están llenos """
        return all(vals.get(field) for field in ['department_id', 'color_id', 'type_id', 'size_id'])

    def _merge_existing_values(self, vals):
        """ Completa los valores faltantes con los datos actuales del producto """
        merged_vals = vals.copy()
        for field in ['department_id', 'color_id', 'type_id', 'size_id']:
            if not merged_vals.get(field):
                merged_vals[field] = getattr(self, field).id
        return merged_vals

    def _generate_consecutive(self):
        """ Genera un consecutivo incremental global sin importar el departamento """
        last_product = self.search([('consecutive', '!=', False)], order="consecutive desc", limit=1)

        if last_product and last_product.consecutive.isdigit():
            last_code = int(last_product.consecutive)
        else:
            last_code = 0  # Si no hay productos, inicia en 1

        new_code = str(last_code + 1).zfill(6)  # Se llena con ceros hasta 6 dígitos
        return new_code

    def _generate_product_code(self, vals):
        """ Genera el código de producto basado en los valores seleccionados """

        def get_code(field_name, default):
            """ Obtiene el código asignado a cada categoría """
            return self.env['barcode.parameter.line'].browse(vals.get(field_name)).codigo if vals.get(field_name) else default

        department_code = get_code('department_id', '00')
        color_code = get_code('color_id', '000')
        type_code = get_code('type_id', '000')
        size_code = get_code('size_id', '000')
        consecutive_code = vals.get('consecutive', '000000')

        return f"{department_code}{type_code}{color_code}{size_code}{consecutive_code}"

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
            'department_id': False,
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
            
    @api.depends('standard_price', 'profit_margin_list')
    def _compute_prices_list(self):
        for product in self:
            if product.standard_price:
                profit_factor = 1 + (product.profit_margin_list / 100)
                product.list_price = product.standard_price * profit_factor
            else:
                product.list_price = 0.0

    @api.depends('standard_price', 'profit_margin_cred')
    def _compute_prices_cred(self):
        for product in self:
            if product.standard_price and product.profit_margin_cred:
                profit_factor = 1 + (product.profit_margin_cred / 100)
                product.credit_price = product.standard_price * profit_factor
            else:
                product.credit_price = 0.0