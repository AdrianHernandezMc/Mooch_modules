import json, logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.addons.decimal_precision import dp
from odoo.tools.misc import format_amount

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
        _logger.info("Iniciando validación de presupuesto para PO %s", self.name)
        
        try:
            BudgetLine = self.env['crossovered.budget.lines']
            AnalyticLine = self.env['account.analytic.line']
        except KeyError as e:
            _logger.error("Error al cargar modelos de presupuesto: %s", str(e))
            self.budget_validated = True
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error en módulo de presupuestos'),
                    'message': _('No se pudo acceder al módulo de presupuestos. Verifique que esté instalado.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        
        today = fields.Date.context_today(self)
        message_lines = []
        has_errors = False
        
        # 1) Validación preliminar
        if not self.order_line:
            raise UserError(_("No hay líneas en el pedido para validar el presupuesto."))
        
        # 2) Calcular totales por cuenta analítica
        totals = {}
        for line in self.order_line:
            if not line.analytic_distribution:
                continue
                
            analytic_dist = line.analytic_distribution
            if isinstance(analytic_dist, str):
                try:
                    analytic_dist = json.loads(analytic_dist)
                except json.JSONDecodeError:
                    continue
            
            if not isinstance(analytic_dist, dict):
                continue
                
            for account_id_str, percentage in analytic_dist.items():
                try:
                    account_id = int(account_id_str)
                    percentage = float(percentage)
                except (ValueError, TypeError):
                    continue
                    
                acct = self.env['account.analytic.account'].browse(account_id)
                if not acct.exists():
                    continue
                    
                amt = line.price_total  * (percentage / 100.0)
                totals[acct] = totals.get(acct, 0.0) + amt

        if not totals:
            raise UserError(_("No se encontraron distribuciones analíticas válidas en las líneas del pedido."))
        
        # 3) Validar contra presupuestos
        for acct, po_amt in totals.items():
            # Buscar línea de presupuesto vigente
            bline = BudgetLine.search([
                ('analytic_account_id', '=', acct.id),
                ('date_from', '<=', today),
                ('date_to', '>=', today),
            ], limit=1)
            
            if not bline:
                message_lines.append(f"""
                <div style="margin-bottom: 15px; color: #f44336;">
                    <h3>❌ {acct.name}</h3>
                    <p>No hay línea de presupuesto para el período actual</p>
                </div>
                """)
                has_errors = True
                continue
            
            # Calcular total comprometido (valor absoluto)
            domain = [
                ('account_id', '=', acct.id),
                ('date', '>=', bline.date_from),
                ('date', '<=', bline.date_to),
            ]
            analytic_lines = AnalyticLine.search(domain)
            total_comprometido = sum(abs(line.amount) for line in analytic_lines)
            
            planned = bline.planned_amount
            nuevo_compromiso = total_comprometido + abs(po_amt)
            diferencia = planned - nuevo_compromiso
            
            # Validación
            if nuevo_compromiso > planned:
                exceso = nuevo_compromiso - planned
                message_lines.append(f"""
                <div style="margin-bottom: 15px; color: #f44336;">
                    <h3>❌ {acct.name}</h3>
                    <table style="width: 100%;">
                        <tr><td style="width: 40%;">• Presupuesto total:</td><td style="font-weight: bold;">{format_amount(self.env, planned, self.currency_id)}</td></tr>
                        <tr><td>• Total comprometido actual:</td><td style="font-weight: bold;">{format_amount(self.env, total_comprometido, self.currency_id)}</td></tr>
                        <tr><td>• Este pedido compromete:</td><td style="font-weight: bold;">{format_amount(self.env, abs(po_amt), self.currency_id)}</td></tr>
                        <tr><td>• Nuevo total comprometido:</td><td style="font-weight: bold;">{format_amount(self.env, nuevo_compromiso, self.currency_id)}</td></tr>
                        <tr><td>• Exceso:</td><td style="font-weight: bold;">{format_amount(self.env, exceso, self.currency_id)}</td></tr>
                    </table>
                </div>
                """)
                has_errors = True
            else:
                message_lines.append(f"""
                <div style="margin-bottom: 15px;">
                    <h3 style="color: #4CAF50;">✓ {acct.name}</h3>
                    <table style="width: 100%;">
                        <tr><td style="width: 40%;">• Presupuesto total:</td><td style="font-weight: bold;">{format_amount(self.env, planned, self.currency_id)}</td></tr>
                        <tr><td>• Total comprometido actual:</td><td style="font-weight: bold; color: #f44336;">{format_amount(self.env, total_comprometido, self.currency_id)}</td></tr>
                        <tr><td>• Este pedido compromete:</td><td style="font-weight: bold; color: #f44336;">{format_amount(self.env, abs(po_amt), self.currency_id)}</td></tr>
                        <tr><td>• Nuevo total comprometido:</td><td style="font-weight: bold; color: #f44336;">{format_amount(self.env, nuevo_compromiso, self.currency_id)}</td></tr>
                        <tr><td>• Diferencia disponible:</td><td style="font-weight: bold; color: {'#f44336' if diferencia < 0 else '#4CAF50'}">{format_amount(self.env, diferencia, self.currency_id)}</td></tr>
                    </table>
                </div>
                """)
        
        # 4) Mostrar resultados en wizard
        if not has_errors:
            self.budget_validated = True
        
        wizard = self.env['budget.validation.wizard'].create({
            'message': """
            <style>
                .budget-table {
                    width: 100%;
                    margin-bottom: 15px;
                }
                .budget-table td {
                    padding: 3px 0;
                }
                .success-account {
                    color: #4CAF50;
                    margin-bottom: 15px;
                }
                .error-account {
                    color: #f44336;
                    margin-bottom: 15px;
                }
            </style>
            """ + ''.join(message_lines)
        })
        
        return {
            'name': _('Resultado de Validación de Presupuesto'),
            'type': 'ir.actions.act_window',
            'res_model': 'budget.validation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'res_id': wizard.id,
            'views': [(False, 'form')],
            'context': self.env.context,
        }

    # Sobrescribes button_confirm para forzar check si no se ha validado
    def button_confirm(self):
        for po in self:
            if not po.budget_validated:
                raise UserError(_("Debes primero “Validar Presupuesto”"))
        return super().button_confirm()
    
    def get_department_budget_data(self):
        BudgetLine = self.env['crossovered.budget.lines']
        AnalyticLine = self.env['account.analytic.line']
        today = fields.Date.context_today(self)
        
        departments = self.env['hr.department'].search([])
        
        result = []
        for dept in departments:
            # Buscar cuentas analíticas asociadas al departamento
            accounts = self.env['account.analytic.account'].search([
                ('department_id', '=', dept.id),
                ('active', '=', True)
            ])
            
            if not accounts:
                continue
                
            total_budget = 0
            total_committed = 0
            for account in accounts:
                # Buscar línea de presupuesto vigente
                bline = BudgetLine.search([
                    ('analytic_account_id', '=', account.id),
                    ('date_from', '<=', today),
                    ('date_to', '>=', today),
                ], limit=1)
                
                if not bline:
                    continue
                    
                # Calcular total comprometido
                domain = [
                    ('account_id', '=', account.id),
                    ('date', '>=', bline.date_from),
                    ('date', '<=', bline.date_to),
                ]
                analytic_lines = AnalyticLine.search(domain)
                total_committed += sum(abs(line.amount) for line in analytic_lines)
                total_budget += bline.planned_amount
            
            if total_budget <= 0:
                continue
                
            available = total_budget - total_committed
            percentage = (total_committed / total_budget * 100)
            
            result.append({
                'department': dept.name,
                'budget_total': total_budget,
                'committed': total_committed,
                'available': available,
                'percentage': percentage,
            })

        return result

    def action_open_discount_wizard(self):
        self.ensure_one()
        return {
            'name': 'Agregar Descuento Global',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.discount.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
            }
        }