# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.osv import expression
import logging

_logger = logging.getLogger(__name__)


LIMIT_CHOICES = [
    ('1000', '1000'),
    ('750', '750'),
    ('500', '500'),
    ('250', '250'),
    ('100', '100'),
    ('50', '50'),
    ('25', '25'),
    ('10', '10'),
]


class ProductSelectorWizard(models.TransientModel):
    _name = 'product.selector.wizard'
    _description = 'Wizard para agregar productos a orden de compra'

    selector_ids = fields.One2many('product.product.selector', 'wizard_id', string='Productos')
    purchase_id = fields.Many2one('purchase.order', string='Orden de Compra')

    search_term = fields.Char(string='Buscar')
    # ⬇️ Lista desplegable descendente; default 1000
    limit_results = fields.Selection(
        selection=LIMIT_CHOICES,
        string='Resultados a mostrar',
        default='1000',
        required=True,
        help="Cantidad de productos a listar y a usar en la búsqueda."
    )

    # Auxiliar para el dominio del M2O en la vista
    dept_param_line_id = fields.Many2one(
        'barcode.parameter.line',
        string='Departamento (usuario)',
        readonly=True,
        help="Línea de parámetro 'Departamento' mapeada desde el hr.department del USUARIO actual."
    )

    # --------------------------
    # Helpers
    # --------------------------
    def _limit_int(self):
        """Convierte el selection string a int (default 1000)."""
        try:
            return int(self.limit_results or '1000')
        except Exception:
            return 1000

    def _product_env_ctx(self):
        # Contexto seguro (no leer purchase_id aquí)
        return {
            'lang': self.env.user.lang,
            'company_id': self.env.company.id,
            'force_company': self.env.company.id,
            'display_default_code': True,
        }

    def _user_hr_department(self):
        # sudo para evitar reglas/permisos en hr.employee durante default_get
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.uid)], limit=1)
        return emp.department_id if emp and emp.department_id else False

    def _map_user_dept_to_param_line(self):
        ParamLine = self.env['barcode.parameter.line']
        hr_dept = self._user_hr_department()
        if not hr_dept:
            return False
        dept_name = (hr_dept.name or '').strip()
        if not dept_name:
            return False
        lines = ParamLine.search([('parameter_id.name', '=', 'Departamento')])
        # exacto
        for line in lines:
            if line.nombre and line.nombre.strip().lower() == dept_name.lower():
                return line
        # parcial
        for line in lines:
            if line.nombre and dept_name.lower() in line.nombre.strip().lower():
                return line
        return False

    def _department_domain_for_products(self):
        # ESTRICTO: solo depto del USUARIO; sin depto -> 0 resultados
        dept_line = self._map_user_dept_to_param_line()
        self.dept_param_line_id = dept_line.id if dept_line else False
        if not dept_line:
            return [('id', '=', 0)]
        return [
            ('purchase_ok', '=', True),
            ('product_tmpl_id.department_id', '=', dept_line.id),
        ]

    def _fetch_products_by_term(self, term, limit):
        Product = self.env['product.product'].with_context(**self._product_env_ctx())
        domain = self._department_domain_for_products()
        if term:
            name_or_code = ['|', ('name', 'ilike', term), ('default_code', 'ilike', term)]
            domain = expression.AND([domain, name_or_code])
        products = Product.search(domain, limit=limit)
        _logger.info("🔒 User=%s | DeptLine=%s | term=%r | limit=%s | encontrados=%s",
                     self.env.user.login,
                     self.dept_param_line_id.display_name if self.dept_param_line_id else None,
                     term, limit, len(products))
        return products

    def _get_vendor_price(self, product, qty=1.0, partner=False, date=False, uom=False):
        """No dependas de self.purchase_id durante default_get; permite inyectar partner/fecha."""
        partner = partner or (self.purchase_id.partner_id if self.purchase_id else False)
        uom = uom or (product.uom_po_id or product.uom_id)
        date = date or (self.purchase_id.date_order if (self.purchase_id and self.purchase_id.date_order) else fields.Date.context_today(self))
        seller = product._select_seller(
            partner_id=partner,
            quantity=qty or 1.0,
            date=date,
            uom_id=uom
        )
        return seller.price if seller else product.standard_price

    # --------------------------
    # Acciones
    # --------------------------
    def action_confirm(self):
        self.ensure_one()
        selected = self.selector_ids.filtered('x_selected')
        if not selected:
            raise UserError(_("Debe seleccionar al menos un producto."))
        for sel in selected:
            product = sel.product_id
            if not product:
                continue
            line_vals = {
                'order_id': self.purchase_id.id if self.purchase_id else False,
                'product_id': product.id,
                'name': product.display_name or product.name,
                'product_uom': (product.uom_po_id or product.uom_id).id,
                'price_unit': sel.price_unit,
                'product_qty': sel.product_qty,
            }
            analytic_account = (
                self.purchase_id.analytic_account_id if self.purchase_id and self.purchase_id.analytic_account_id else
                getattr(product, 'analytic_account_id', False) or
                getattr(product.categ_id, 'computed_analytic_account_id', False)
            )
            if analytic_account:
                line_vals['analytic_distribution'] = {str(analytic_account.id): 100.0}
            line = self.env['purchase.order.line'].create(line_vals)
            line.write({'price_unit': sel.price_unit, 'product_qty': sel.product_qty})
        return {'type': 'ir.actions.act_window_close'}

    # --------------------------
    # Defaults (carga inicial)
    # --------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        purchase = self.env.context.get('active_id')
        po = self.env['purchase.order'].browse(purchase) if purchase else False
        po_partner = po.partner_id if po else False
        po_date = po.date_order if po else False

        # Crear tmp con purchase_id (para vista), y limit_results ya por default '1000'
        tmp = self.new({'purchase_id': purchase, 'limit_results': '1000'})

        # fija dept_param_line_id (estricto por depto usuario)
        _ = tmp._department_domain_for_products()

        initial_limit = 1000  # ← pedido: 1000 registros iniciales
        products = tmp._fetch_products_by_term(term=None, limit=initial_limit)

        lines = [(0, 0, {
            'product_id': p.id,
            'product_qty': 1.0,
            # pasar partner/fecha explícitos para evitar recursión
            'price_unit': tmp._get_vendor_price(p, qty=1.0, partner=po_partner, date=po_date),
            'x_selected': False,
        }) for p in products]

        res.update({
            'purchase_id': purchase,
            'dept_param_line_id': tmp.dept_param_line_id.id if tmp.dept_param_line_id else False,
            'limit_results': '1000',
            'selector_ids': lines,
        })
        return res

    # --------------------------
    # Onchange búsqueda / límite
    # --------------------------
    @api.onchange('search_term', 'limit_results')
    def _onchange_search_term(self):
        sel = self.selector_ids.filtered(lambda l: l.x_selected and l.product_id)
        sel_ids = set(sel.mapped('product_id').ids)
        sel_cmds = [(0, 0, {
            'product_id': l.product_id.id,
            'product_qty': l.product_qty,
            'price_unit': l.price_unit,
            'x_selected': True,
        }) for l in sel]

        limit = self._limit_int()
        products = self._fetch_products_by_term(self.search_term, limit)
        nuevos = products.filtered(lambda p: p.id not in sel_ids)

        po = self.purchase_id
        po_partner = po.partner_id if po else False
        po_date = po.date_order if po and po.date_order else False

        new_cmds = [(0, 0, {
            'product_id': p.id,
            'product_qty': 1.0,
            'price_unit': self._get_vendor_price(p, qty=1.0, partner=po_partner, date=po_date),
            'x_selected': False,
        }) for p in nuevos]

        self.selector_ids = [(5, 0, 0)] + sel_cmds + new_cmds


class ProductProductSelector(models.TransientModel):
    _name = 'product.product.selector'
    _description = 'Línea del selector'
    _order = 'product_id'

    wizard_id = fields.Many2one('product.selector.wizard', string='Wizard')
    x_selected = fields.Boolean(string='Seleccionado')

    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        domain="[('purchase_ok','=',True),('product_tmpl_id.department_id','=', parent.dept_param_line_id)]",
        options="{'no_create': True, 'no_create_edit': True}",
    )

    name = fields.Char(related='product_id.name', string='Nombre', store=False)
    default_code = fields.Char(related='product_id.default_code', string='Código Interno', store=False)
    barcode = fields.Char(related='product_id.barcode', string='Código de barras', store=False)

    dept_line_id = fields.Many2one(
        'barcode.parameter.line',
        string='Departamento',
        related='product_id.product_tmpl_id.department_id',
        store=False,
        readonly=True,
    )

    product_qty = fields.Float(string='Cantidad', default=1.0)
    price_unit = fields.Float(string='Costo Unitario')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.product_qty = rec.product_qty or 1.0
                wiz = rec.wizard_id
                if wiz:
                    po = wiz.purchase_id
                    rec.price_unit = wiz._get_vendor_price(
                        rec.product_id,
                        qty=rec.product_qty,
                        partner=(po.partner_id if po else False),
                        date=(po.date_order if po and po.date_order else False),
                    )
                else:
                    rec.price_unit = rec.product_id.standard_price
