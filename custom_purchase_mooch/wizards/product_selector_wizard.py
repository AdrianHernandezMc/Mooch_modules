# wizards/product_selector_wizard.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime

class ProductSelectorWizard(models.TransientModel):
    _name = 'product.selector.wizard'
    _description = 'Wizard para agregar productos a orden de compra'

    selector_ids = fields.One2many('product.product.selector', 'wizard_id', string='Productos')
    purchase_id = fields.Many2one('purchase.order', string='Orden de Compra')
    search_term = fields.Char(string='Buscar')
    limit_results = fields.Integer(string='Límite resultados', default=200)

    def _product_env_ctx(self):
        """Contexto como lo usa Odoo en compras para mejorar name_search:
        - partner_id: prioriza códigos/nombres del proveedor
        - display_default_code: muestra [CODE] al buscar
        - force_company/company_id/lang: coherencia multi-compañía/idioma
        """
        return {
            'lang': self.env.user.lang,
            'partner_id': self.purchase_id.partner_id.id if self.purchase_id and self.purchase_id.partner_id else False,
            'company_id': self.env.company.id,
            'force_company': self.env.company.id,
            'display_default_code': True,
        }

    def _fetch_products_by_term(self, term, limit):
        """Usa name_search para comportarse como los Many2one de Odoo."""
        Product = self.env['product.product'].with_context(**self._product_env_ctx())
        if term:
            # name_search respeta: nombre, default_code, barcode, supplierinfo (con partner_id)
            pairs = Product.name_search(term, operator='ilike', limit=limit)
            ids = [pid for pid, _name in pairs]
            # browse conserva el orden de ids tal cual vienen de name_search
            products = Product.browse(ids)
        else:
            # Si no hay término, no saturamos: devolvemos un pequeño set inicial
            products = Product.search([], limit=min(limit, 20))
        return products

    def _get_vendor_price(self, product, qty=1.0):
        """Obtiene precio de proveedor si existe; si no, usa standard_price."""
        partner = self.purchase_id.partner_id if self.purchase_id else False
        uom = product.uom_po_id or product.uom_id
        seller = product._select_seller(
            partner_id=partner,
            quantity=qty or 1.0,
            date=self.purchase_id.date_order or fields.Date.context_today(self),
            uom_id=uom
        )
        if seller:
            # aplicar precio del proveedor respetando unidad
            price = seller.price
            # si hay descuentos/moneda/etc., Odoo usualmente recalcula en onchange;
            # aquí lo dejamos simple (precio base del proveedor).
            return price
        return product.standard_price

    def action_confirm(self):
        self.ensure_one()
        selected = self.selector_ids.filtered('x_selected')
        if not selected:
            raise UserError(_("Debe seleccionar al menos un producto."))

        for sel in selected:
            # Valida producto
            product = sel.product_id
            if not product:
                continue

            # Valores base de la línea
            line_vals = {
                'order_id': self.purchase_id.id,
                'product_id': product.id,
                'name': product.display_name or product.name,
                'product_uom': (product.uom_po_id or product.uom_id).id,
                'price_unit': sel.price_unit,
                'product_qty': sel.product_qty,
            }

            # Analítica (igual que tu lógica actual)
            analytic_account = (
                self.purchase_id.analytic_account_id
                or getattr(product, 'analytic_account_id', False)
                or getattr(product.categ_id, 'computed_analytic_account_id', False)
            )
            if analytic_account:
                line_vals['analytic_distribution'] = {str(analytic_account.id): 100.0}

            # Crea línea
            line = self.env['purchase.order.line'].create(line_vals)

            # Mantener valores del usuario (qty y precio final)
            line.write({
                'price_unit': sel.price_unit,
                'product_qty': sel.product_qty,
            })

        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        purchase = self.env.context.get('active_id')

        # No cargamos TODO: mostramos un lote corto inicial (como "sugerencias")
        initial_limit = 200
        products = self._fetch_products_by_term(term=None, limit=initial_limit)

        lines = []
        for p in products:
            lines.append((0, 0, {
                'product_id': p.id,
                'product_qty': 1.0,
                'price_unit': self._get_vendor_price(p, qty=1.0),
                'x_selected': False,
            }))

        res.update({
            'purchase_id': purchase,
            'selector_ids': lines,
        })
        return res

    @api.onchange('search_term', 'limit_results')
    def _onchange_search_term(self):
        """Reemplaza listado usando name_search como Odoo, conservando seleccionados."""
        # 1) Conservar los ya seleccionados con sus valores
        sel = self.selector_ids.filtered(lambda l: l.x_selected and l.product_id)
        sel_ids = set(sel.mapped('product_id').ids)
        sel_cmds = [
            (0, 0, {
                'product_id': l.product_id.id,
                'product_qty': l.product_qty,
                'price_unit': l.price_unit,
                'x_selected': True,
            })
            for l in sel
        ]

        # 2) Buscar nuevos productos con name_search (comportamiento Odoo)
        limit = self.limit_results or 50
        products = self._fetch_products_by_term(self.search_term, limit)

        # Excluir los ya seleccionados
        nuevos = products.filtered(lambda p: p.id not in sel_ids)

        # 3) Preparar cmds para nuevos resultados
        new_cmds = []
        for p in nuevos:
            new_cmds.append((0, 0, {
                'product_id': p.id,
                'product_qty': 1.0,
                'price_unit': self._get_vendor_price(p, qty=1.0),
                'x_selected': False,
            }))

        # 4) Reemplazar la lista (vaciar y volver a cargar)
        self.selector_ids = [(5, 0, 0)] + sel_cmds + new_cmds


class ProductProductSelector(models.TransientModel):
    _name = 'product.product.selector'
    _description = 'Línea del selector'
    _order = 'product_id'

    wizard_id = fields.Many2one('product.selector.wizard', string='Wizard')
    x_selected = fields.Boolean(string='Seleccionado')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    name = fields.Char(related='product_id.name', string='Nombre', store=False)
    default_code = fields.Char(related='product_id.default_code', string='Código Interno', store=False)
    barcode = fields.Char(related='product_id.barcode', string='Código de barras', store=False)
    product_qty = fields.Float(string='Cantidad', default=1.0)
    price_unit = fields.Float(string='Costo Unitario')
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Cuando el usuario cambie de producto manualmente en la línea del wizard,
        pre-cargar costo del proveedor (o standard_price) y qty = 1.
        """
        for rec in self:
            if rec.product_id:
                rec.product_qty = rec.product_qty or 1.0
                # Si el wizard existe, podemos acceder a partner para precio proveedor
                wiz = rec.wizard_id
                if wiz:
                    rec.price_unit = wiz._get_vendor_price(rec.product_id, qty=rec.product_qty)
                else:
                    rec.price_unit = rec.product_id.standard_price
