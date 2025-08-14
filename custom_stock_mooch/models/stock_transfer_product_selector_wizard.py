# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

SEARCH_LIMIT_DEFAULT = 120

class StockTransferProductSelectorWizard(models.TransientModel):
    _name = 'stock.transfer.product.selector'
    _description = 'Selector de productos para transferencias internas'

    # Igual que en Compras: "selector_ids"
    selector_ids = fields.One2many(
        'stock.transfer.product.selector.line', 'wizard_id', string='Productos'
    )
    picking_id = fields.Many2one('stock.picking', string='Transferencia')
    search_term = fields.Char(string='Buscar')

    # Info de contexto (solo lectura)
    location_id = fields.Many2one(related='picking_id.location_id', string='Ubicación Origen', readonly=True)
    location_dest_id = fields.Many2one(related='picking_id.location_dest_id', string='Ubicación Destino', readonly=True)

    # --- Acciones ---
    def action_confirm(self):
        self.ensure_one()
        if not self.picking_id or self.picking_id.picking_type_id.code != 'internal':
            raise UserError(_("Este selector solo aplica a transferencias internas."))

        selected = self.selector_ids.filtered('x_selected')
        if not selected:
            raise UserError(_("Debe seleccionar al menos un producto."))

        Move = self.env['stock.move']
        for sel in selected:
            if sel.product_qty <= 0:
                continue
            Move.create({
                'name': sel.product_id.display_name,
                'picking_id': self.picking_id.id,
                'product_id': sel.product_id.id,
                'product_uom': sel.product_id.uom_id.id,
                'product_uom_qty': sel.product_qty,
                'location_id': self.location_id.id,
                'location_dest_id': self.location_dest_id.id,
                'company_id': self.picking_id.company_id.id,
                'procure_method': 'make_to_stock',
            })

        # Intentar reservar (si procede)
        try:
            self.picking_id.action_assign()
        except Exception:
            pass

        return {'type': 'ir.actions.act_window_close'}

    def action_search(self):
        """Carga resultados sin perder lo seleccionado. No busca si no hay término."""
        self.ensure_one()

        keep_cmds = [(0, 0, {
            'product_id': l.product_id.id,
            'product_qty': l.product_qty,
            'price_unit': l.price_unit,
            'x_selected': True,
        }) for l in self.selector_ids.filtered('x_selected')]
        already_ids = set(l.product_id.id for l in self.selector_ids.filtered('x_selected'))

        if not (self.search_term and self.search_term.strip()):
            self.selector_ids = [(5, 0, 0)] + keep_cmds
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        Product = self.env['product.product']
        dom = ['|', '|',
            ('default_code', 'ilike', self.search_term),
            ('name', 'ilike', self.search_term),
            ('barcode', 'ilike', self.search_term)]
        prods = Product.search(dom, limit=120)

        nuevos = prods.filtered(lambda p: p.id not in already_ids)
        new_cmds = [(0, 0, {
            'product_id': p.id,
            'product_qty': 1.0,
            'price_unit': p.standard_price,
            'x_selected': False,
        }) for p in nuevos]

        self.selector_ids = [(5, 0, 0)] + keep_cmds + new_cmds

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # --- Inicialización ---
    @api.model
    def default_get(self, fields_list):
        """Abrir vacío: no cargamos productos al inicio."""
        res = super().default_get(fields_list)
        res.update({
            'picking_id': self.env.context.get('active_id'),
        })
        return res


class StockTransferProductSelectorLine(models.TransientModel):
    _name = 'stock.transfer.product.selector.line'
    _description = 'Línea del selector de transferencia'
    _order = 'product_id'

    wizard_id = fields.Many2one('stock.transfer.product.selector', string='Wizard')
    x_selected = fields.Boolean(string='Seleccionado')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    name = fields.Char(related='product_id.name', string='Nombre', readonly=True)
    default_code = fields.Char(related='product_id.default_code', string='Código', readonly=True)
    uom_id = fields.Many2one(related='product_id.uom_id', string='UdM', readonly=True)
    product_qty = fields.Float(string='Cantidad', default=1.0)
    # Para que la vista se sienta igual a Compras (aunque no lo use el move):
    price_unit = fields.Float(string='Costo Unitario', default=lambda self: self.product_id.standard_price)
