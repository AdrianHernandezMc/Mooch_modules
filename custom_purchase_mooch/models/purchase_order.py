import json, logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.addons.decimal_precision import dp

_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    invoice_tag_ids = fields.Many2many(
        'purchase.invoice.tag',
        'purchase_order_invoice_tag_rel',
        'order_id',
        'tag_id',
        string="Facturas Proveedor",
        help="Añade aquí tantas referencias de factura como necesites",
    )

    discount_global = fields.Float(
        string="Descuento Global (%)",
        default=0.0,
        digits=dp.get_precision('Discount'),
        help="Porcentaje que se aplicará a todas las líneas",
    )

    total_discount = fields.Monetary(
        string="Total Descuento",
        compute="_compute_total_discount",
        store=True,
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Departamento',
        help='Departamento responsable de este pedido',
    )

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string="Cuenta Analítica",
        help="Cuenta analítica sobre la que se controlará el presupuesto",
    )

    budget_validated = fields.Boolean(
        string="Presupuesto Validado",
        default=False,
        copy=False,
    )
    show_confirm_button = fields.Boolean(string="Mostrar Confirmar", compute='_compute_show_confirm_button', store=False)

    @api.depends('order_line.price_unit', 'order_line.product_qty', 'order_line.discount')
    def _compute_total_discount(self):
        for order in self:
            total = sum(
                line.price_unit * line.product_qty * line.discount / 100.0
                for line in order.order_line
            )
            order.total_discount = total

    @api.onchange('discount_global')
    def _onchange_discount_global(self):
        for line in self.order_line:
            line.discount = self.discount_global or 0.0

    def action_open_product_selector(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Selector de Productos',
            'res_model': 'product.selector.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_id': self.id,
            },
        }

    @api.onchange('order_line')
    def _onchange_order_lines_analytic(self):
        for po in self:
            accounts = po.order_line.mapped('analytic_account_id')
            po.analytic_account_id = accounts[0] if len(accounts)==1 else False

    @api.depends('budget_validated')
    def _compute_show_confirm_button(self):
        for order in self:
            order.show_confirm_button = order.budget_validated

    def action_check_budget(self):
        self.ensure_one()
        _logger.info("🚧 Validating budget for PO %s", self.name)
        today = fields.Date.context_today(self)
        # agrupamos por cuenta
        totals = {}
        for line in self.order_line:
            base = line.price_unit * line.product_qty * (1 - (line.discount or 0.0) / 100.0)
            raw = line.analytic_distribution or []
            # 1) string → JSON
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except ValueError:
                    raw = []
            # 2) dict → lista de dicts
            if isinstance(raw, dict):
                raw = [{'account_id': int(k), 'percentage': v} for k, v in raw.items()]
            # 3) ahora raw debería ser lista
            dist_list = []
            if isinstance(raw, list):
                for elt in raw:
                    if isinstance(elt, dict) and 'account_id' in elt:
                        dist_list.append({
                            'account_id': int(elt['account_id']),
                            'percentage': float(elt.get('percentage', 0.0))
                        })
                    elif (isinstance(elt, (list, tuple)) and len(elt) >= 2):
                        # ej. [account_id, percentage]
                        dist_list.append({
                            'account_id': int(elt[0]),
                            'percentage': float(elt[1])
                        })
                    else:
                        _logger.warning("Skipping invalid dist chunk %r on line %s", elt, line.id)
            # si no hay distribución, salto
            if not dist_list:
                continue
            # acumulo por cuenta
            for chunk in dist_list:
                acc = self.env['account.analytic.account'].browse(chunk['account_id'])
                if not acc:
                    continue
                amt = base * (chunk['percentage'] / 100.0)
                totals[acc] = totals.get(acc, 0.0) + amt

        BudgetLine = self.env['crossovered.budget.lines']
        for acct, po_amt in totals.items():
            bline = BudgetLine.search([
                ('analytic_account_id', '=', acct.id),
                ('date_from', '<=', today),
                ('date_to',   '>=', today),
            ], limit=1)
            if not bline:
                raise UserError(_("No hay línea de presupuesto para “%s” en %s") % (acct.name, today))
            committed = sum(self.env['account.analytic.line'].search([
                ('account_id', '=', acct.id),
                ('date', '>=', bline.date_from),
                ('date', '<=', bline.date_to),
            ]).mapped('amount'))
            _logger.info("Budget %s: planned=%s, committed=%s, this_po=%s",
                         acct.name, bline.planned_amount, committed, po_amt)
            if committed + po_amt > bline.planned_amount:
                raise UserError(_(
                    "Presupuesto excedido para “%s”: planificado %s, comprometido %s, este PO añade %s"
                ) % (acct.name, bline.planned_amount, committed, po_amt))

        # todo OK
        self.budget_validated = True
        _logger.info("Presupuesto validado para %s", self.name)
        return True
    

    # Sobrescribes button_confirm para forzar check si no se ha validado
    def button_confirm(self):
        for po in self:
            if not po.budget_validated:
                raise UserError(_("Debes primero “Validar Presupuesto”"))
        return super().button_confirm()