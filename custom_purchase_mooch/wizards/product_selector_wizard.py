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
        # filtrar los seleccionados
        selected = self.selector_ids.filtered('x_selected')
        if not selected:
            raise UserError("Debe seleccionar al menos un producto.")
        for sel in selected:
            # 1) crear la línea (aquí Odoo aplica sus onchanges internos)
            line = self.env['purchase.order.line'].create({
                'order_id':    self.purchase_id.id,
                'product_id':  sel.product_id.id,
                'name':        sel.product_id.name,
                'product_uom': sel.product_id.uom_po_id.id,
                'price_unit':  sel.price_unit,
                'product_qty': sel.product_qty,
            })
            # 2) sobrescribir de golpe con los valores que puso el usuario
            line.write({
                'price_unit':  sel.price_unit,
                'product_qty': sel.product_qty,
            })
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        purchase = self.env.context.get('active_id')
        products = self.env['product.product'].search([])
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
        # 1) Sacar las líneas ya seleccionadas (con sus qty y price tal cual las modificaste)
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

        # 2) Buscar nuevos productos (filtrados por texto) y excluir ya seleccionados
        domain = []
        if self.search_term:
            domain = ['|',
                      ('name', 'ilike', self.search_term),
                      ('default_code', 'ilike', self.search_term)]
        prods     = self.env['product.product'].search(domain)
        nuevos    = prods.filtered(lambda p: p.id not in sel_ids)
        new_cmds  = [
            (0, 0, {
                'product_id':  p.id,
                'product_qty': 1.0,
                'price_unit':  p.standard_price,
                'x_selected':  False,
            })
            for p in nuevos
        ]

        # 3) Reemplazar la lista entero de una: vaciar (5) y luego todos los comandos
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