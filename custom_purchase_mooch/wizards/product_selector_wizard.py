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
        selected = self.selector_ids.filtered('x_selected')
        if not selected:
            raise UserError("Debe seleccionar al menos un producto.")
        
        for sel in selected:
            # Preparar valores base
            line_vals = {
                'order_id': self.purchase_id.id,
                'product_id': sel.product_id.id,
                'name': sel.product_id.name,
                'product_uom': sel.product_id.uom_po_id.id,
                'price_unit': sel.price_unit,
                'product_qty': sel.product_qty,
            }
            
            # Lógica adaptada de _onchange_product_set_analytic
            analytic_account = (
                self.purchase_id.analytic_account_id or
                getattr(sel.product_id, 'analytic_account_id', False) or
                getattr(sel.product_id.categ_id, 'computed_analytic_account_id', False)
            )
            
            if analytic_account:
                line_vals['analytic_distribution'] = {str(analytic_account.id): 100.0}
            
            # Crear la línea
            line = self.env['purchase.order.line'].create(line_vals)
            
            # Mantener valores específicos del usuario
            line.write({
                'price_unit': sel.price_unit,
                'product_qty': sel.product_qty,
            })
            
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        purchase = self.env.context.get('active_id')

        # No cargar todos los productos de golpe
        # Solo mostrar los primeros 20 como ejemplo
        products = self.env['product.product'].with_context(prefetch_fields=False).search([], limit=20)
        lines = [
            (0, 0, {
                'product_id': p.id,
                'product_qty': 1.0,
                'price_unit': p.standard_price,
            })
            for p in products
        ]
        res.update({
            'purchase_id': purchase,
            'selector_ids': lines,
        })
        return res

    @api.onchange('search_term')
    def _onchange_search_term(self):
        sel = self.selector_ids.filtered(lambda l: l.x_selected)
        sel_ids   = sel.mapped('product_id.id')
        sel_cmds  = [
            (0, 0, {
                'product_id':  l.product_id.id,
                'product_qty': l.product_qty,
                'price_unit':  l.price_unit,
                'x_selected':  True,
            })
            for l in sel
        ]

        domain = []
        if self.search_term:
            domain = ['|',
                    ('name', 'ilike', self.search_term),
                    ('default_code', 'ilike', self.search_term)]

        # 🔹 Limitar resultados
        prods = self.env['product.product'].with_context(prefetch_fields=False).search(domain, limit=50)
        nuevos = prods.filtered(lambda p: p.id not in sel_ids)

        new_cmds = [
            (0, 0, {
                'product_id':  p.id,
                'product_qty': 1.0,
                'price_unit':  p.standard_price,
                'x_selected':  False,
            })
            for p in nuevos
        ]

        self.selector_ids = [(5, 0, 0)] + sel_cmds + new_cmds


class ProductProductSelector(models.TransientModel):
    _name = 'product.product.selector'
    _description = 'Línea del selector'
    _order = 'product_id'

    wizard_id = fields.Many2one('product.selector.wizard', string='Wizard')
    x_selected = fields.Boolean(string='Seleccionado')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    name = fields.Char(related='product_id.name', string='Nombre')
    default_code = fields.Char(related='product_id.default_code', string='Código Interno')
    product_qty = fields.Float(string='Cantidad', default=1.0)
    price_unit = fields.Float(string='Costo Unitario', default=lambda self: self.product_id.standard_price)