# wizards/product_selector_wizard.py
from odoo import models, fields, api
from odoo.exceptions import UserError

class ProductSelectorWizard(models.TransientModel):
    _name = 'product.selector.wizard'
    _description = 'Wizard para agregar productos a orden de compra'

    selector_ids = fields.One2many('product.product.selector', 'wizard_id', string='Productos')
    purchase_id = fields.Many2one('purchase.order', string='Orden de Compra')
    search_term = fields.Char(string='Buscar')

    def action_confirm(self):
        self.ensure_one()
        selected_products = self.selector_ids.filtered(lambda p: p.x_selected)
        if not selected_products:
            raise UserError("Debe seleccionar al menos un producto.")

        for selector in selected_products:
            self.purchase_id.order_line.create({
                'order_id': self.purchase_id.id,
                'product_id': selector.product_id.id,
                'name': selector.product_id.name,
                'product_uom': selector.product_id.uom_po_id.id,
                'price_unit': selector.product_id.standard_price,
                'product_qty': 1,
            })
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        purchase_id = self.env.context.get('active_id')
        products = self.env['product.product'].search([])
        lines = [(0, 0, {
            'product_id': p.id,
        }) for p in products]

        res.update({
            'purchase_id': purchase_id,
            'selector_ids': lines
        })
        return res

    @api.onchange('search_term')
    def _onchange_search_term(self):
        if self.search_term:
            products = self.env['product.product'].search([
                '|', ('name', 'ilike', self.search_term),
                    ('default_code', 'ilike', self.search_term)
            ])
        else:
            products = self.env['product.product'].search([])

        self.selector_ids = [(5, 0, 0)]
        self.selector_ids = [(0, 0, {'product_id': p.id}) for p in products]

class ProductProductSelector(models.TransientModel):
    _name = 'product.product.selector'
    _description = 'Línea del selector'
    _order = 'product_id'

    wizard_id = fields.Many2one('product.selector.wizard', string='Wizard')
    x_selected = fields.Boolean(string='Seleccionado')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    name = fields.Char(related='product_id.name', string='Nombre')
    default_code = fields.Char(related='product_id.default_code', string='Código Interno')
