# -*- coding: utf-8 -*-
import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.addons.decimal_precision import dp
from odoo.tools.misc import format_amount

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # =========================
    #      CAMPOS EXTRAS
    # =========================
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
        store=True,
        readonly=True,
        compute='_compute_department_from_budget',
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

    show_confirm_button = fields.Boolean(
        string="Mostrar Confirmar",
        compute='_compute_show_confirm_button',
        store=False
    )

    qty_total_order = fields.Float(
        string='Conteo total de cantidades',
        compute='_compute_qty_total_order',
        digits='Product Unit of Measure',
        help='Suma de las cantidades de las líneas de la orden, excluyendo secciones y notas.',
        store=True,
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Solicitante',
        help='persona solicitante y responsable de este pedido',
        store=True,
        required=True
    )

    # =========================
    #        COMPUTES
    # =========================
    @api.depends('order_line.price_unit', 'order_line.product_qty', 'order_line.discount')
    def _compute_total_discount(self):
        for order in self:
            total = sum(
                line.price_unit * line.product_qty * line.discount / 100.0
                for line in order.order_line
            )
            order.total_discount = total

    # =========================
    #        ONCHANGES
    # =========================
    @api.onchange('discount_global')
    def _onchange_discount_global(self):
        for line in self.order_line:
            line.discount = self.discount_global or 0.0

    @api.onchange('order_line')
    def _onchange_order_lines_analytic(self):
        for po in self:
            accounts = po.order_line.mapped('analytic_account_id')
            po.analytic_account_id = accounts[0] if len(accounts) == 1 else False

    @api.onchange('order_line', 'order_line.product_qty', 'order_line.display_type')
    def _onchange_qty_total_order(self):
        for order in self:
            order.qty_total_order = sum(
                l.product_qty for l in order.order_line if not l.display_type
            )

    @api.depends('budget_validated')
    def _compute_show_confirm_button(self):
        for order in self:
            order.show_confirm_button = order.budget_validated

    @api.depends('order_line.product_qty', 'order_line.display_type')
    def _compute_qty_total_order(self):
        for order in self:
            order.qty_total_order = sum(
                l.product_qty for l in order.order_line if not l.display_type
            )

    # =========================
    #       ACCIONES UI
    # =========================
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

    # =========================
    #        HELPERS NUEVOS
    # =========================
    def _get_ref_date_for_budget(self):
        """
        Fecha de referencia para elegir la línea de presupuesto: usa la fecha de la PO.
        Si no existe, usa ahora.
        """
        ref_dt = self.date_order or fields.Datetime.now()
        return fields.Date.to_date(ref_dt)

    def _get_budget_line_for_date(self, analytic_account, ref_date):
        """
        Devuelve la línea de presupuesto vigente para la cuenta en ref_date.
        """
        BudgetLine = self.env['crossovered.budget.lines']
        return BudgetLine.search([
            ('analytic_account_id', '=', analytic_account.id),
            ('date_from', '<=', ref_date),
            ('date_to', '>=', ref_date),
        ], limit=1)

    def _get_committed_from_invoices_period(self, analytic_account, date_from, date_to):
        """
        Comprometido solo por facturas de proveedor POSTEADAS en el periodo del presupuesto,
        usando account.analytic.line enlazada a apuntes contables.

        Notas:
          - Filtramos por move_line_id.parent_state = 'posted' (estado del asiento).
          - Filtramos por move_type in ('in_invoice','in_refund').
          - Costos (amount negativo) → sumamos -amount; refunds restan.
        """
        AnalyticLine = self.env['account.analytic.line']
        domain = [
            ('account_id', '=', analytic_account.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('move_line_id', '!=', False),
            ('move_line_id.parent_state', '=', 'posted'),
            ('move_line_id.move_id.move_type', 'in', ('in_invoice', 'in_refund')),
        ]
        lines = AnalyticLine.search(domain)
        committed = sum((-l.amount) for l in lines)
        return max(committed, 0.0)

    # =========================
    #     VALIDACIÓN PRESUP.
    # =========================
    def action_check_budget(self):
        self.ensure_one()
        _logger.info("Iniciando validación de presupuesto para PO %s", self.name)

        try:
            BudgetLine = self.env['crossovered.budget.lines']
            AnalyticLine = self.env['account.analytic.line']  # noqa: F841
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

        # === Usar el periodo de presupuesto según la fecha de la PO (no 'hoy')
        ref_date = self._get_ref_date_for_budget()

        message_lines = []
        has_errors = False

        # 1) Identificar descuentos (líneas negativas) de ESTA PO
        discount_lines = self.order_line.filtered(lambda l: l.price_total < 0)
        total_discount = abs(sum(discount_lines.mapped('price_total'))) if discount_lines else 0.0

        # 2) Resumen financiero (tal como lo tenías)
        subtotal_sin_descuento = sum(line.price_subtotal for line in self.order_line if line.price_total >= 0)
        subtotal_con_descuento = subtotal_sin_descuento - total_discount
        iva_amount = sum(line.price_tax for line in self.order_line if line.price_total >= 0)
        total = subtotal_con_descuento + iva_amount

        message_lines.append(f"""
        <div style="margin-bottom: 15px; background-color: #f8f9fa; padding: 10px; border-radius: 5px;">
            <h3>💲 Resumen Orden de Compra</h3>
            <table style="width: 100%;">
                <tr><td style="width: 40%;">Subtotal (antes de descuento):</td><td style="font-weight: bold;">{format_amount(self.env, subtotal_sin_descuento, self.currency_id)}</td></tr>
                <tr><td>Total Descuentos:</td><td style="font-weight: bold; color: #4CAF50;">-{format_amount(self.env, total_discount, self.currency_id)}</td></tr>
                <tr><td>Subtotal (con descuento):</td><td style="font-weight: bold; border-top: 1px solid #ddd;">{format_amount(self.env, subtotal_con_descuento, self.currency_id)}</td></tr>
                <tr><td>IVA (16%):</td><td style="font-weight: bold;">{format_amount(self.env, iva_amount, self.currency_id)}</td></tr>
                <tr><td>Total:</td><td style="font-weight: bold; border-top: 1px solid #ddd;">{format_amount(self.env, total, self.currency_id)}</td></tr>
            </table>
        </div>
        """)

        # 3) Procesar líneas para presupuesto (excluyendo descuentos) con prorrateo analítico
        totals = {}
        for line in self.order_line:
            if line.price_total < 0:
                continue
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

                amt = line.price_total * (percentage / 100.0)  # mantiene tu lógica (con IVA)
                totals[acct] = totals.get(acct, 0.0) + amt

        if not totals:
            raise UserError(_("No se encontraron distribuciones analíticas válidas en las líneas del pedido."))

        # 4) Validación contra presupuestos (con periodo por fecha de la PO y comprometido por facturas posteadas)
        for acct, po_amt in totals.items():
            # Línea del presupuesto que cubre la fecha de esta PO
            bline = self._get_budget_line_for_date(acct, ref_date)
            if not bline:
                message_lines.append(f"""
                <div style="margin-bottom: 15px; color: #f44336;">
                    <h3>❌ {acct.name}</h3>
                    <p>No hay línea de presupuesto para el período que cubre la fecha del pedido ({ref_date}).</p>
                </div>
                """)
                has_errors = True
                continue

            # Comprometido actual SOLO por facturas posteadas del periodo (trimestre presupuestal)
            total_comprometido = self._get_committed_from_invoices_period(
                analytic_account=acct,
                date_from=bline.date_from,
                date_to=bline.date_to,
            )

            # Descuentos de ESTA ORDEN prorrateados a esta cuenta
            account_discount = 0.0
            for d_line in discount_lines:
                if not d_line.analytic_distribution:
                    continue
                d_dist = d_line.analytic_distribution
                if isinstance(d_dist, str):
                    try:
                        d_dist = json.loads(d_dist)
                    except json.JSONDecodeError:
                        continue
                if str(acct.id) in d_dist:
                    account_discount += abs(d_line.price_total) * (float(d_dist[str(acct.id)]) / 100.0)

            # Montos ajustados de ESTA ORDEN
            monto_bruto = abs(po_amt)
            monto_neto = max(0, monto_bruto - account_discount)
            nuevo_compromiso = total_comprometido + monto_neto
            diferencia = bline.planned_amount - nuevo_compromiso

            # Render de resultados por cuenta
            if nuevo_compromiso > bline.planned_amount:
                exceso = nuevo_compromiso - bline.planned_amount
                message_lines.append(f"""
                <div style="margin-bottom: 15px; color: #f44336;">
                    <h3>❌ {acct.name}</h3>
                    <table style="width: 100%;">
                        <tr><td style="width: 40%;">• Presupuesto total:</td><td style="font-weight: bold;">{format_amount(self.env, bline.planned_amount, self.currency_id)}</td></tr>
                        <tr><td>• Total comprometido actual:</td><td style="font-weight: bold;">{format_amount(self.env, total_comprometido, self.currency_id)}</td></tr>
                        <tr><td>• Este pedido compromete:</td><td style="font-weight: bold;">{format_amount(self.env, monto_neto, self.currency_id)}</td></tr>
                        <tr><td>• Descuento aplicado:</td><td style="font-weight: bold; color: #4CAF50;">-{format_amount(self.env, account_discount, self.currency_id)}</td></tr>
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
                        <tr><td style="width: 40%;">• Presupuesto total:</td><td style="font-weight: bold;">{format_amount(self.env, bline.planned_amount, self.currency_id)}</td></tr>
                        <tr><td>• Total comprometido actual:</td><td style="font-weight: bold; color: #f44336;">{format_amount(self.env, total_comprometido, self.currency_id)}</td></tr>
                        <tr><td>• Este pedido compromete:</td><td style="font-weight: bold; color: #f44336;">{format_amount(self.env, monto_neto, self.currency_id)}</td></tr>
                        <tr><td>• Descuento aplicado:</td><td style="font-weight: bold; color: #4CAF50;">-{format_amount(self.env, account_discount, self.currency_id)}</td></tr>
                        <tr><td>• Nuevo total comprometido:</td><td style="font-weight: bold; color: #f44336;">{format_amount(self.env, nuevo_compromiso, self.currency_id)}</td></tr>
                        <tr><td>• Diferencia disponible:</td><td style="font-weight: bold; color: {'#f44336' if diferencia < 0 else '#4CAF50'}">
                            {format_amount(self.env, diferencia, self.currency_id)}
                        </td></tr>
                    </table>
                </div>
                """)

        # 5) Wizard con resultados
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

    # =========================
    #       CONFIRMACIÓN
    # =========================
    def button_confirm(self):
        for po in self:
            if not po.budget_validated:
                raise UserError(_("Debes primero “Validar Presupuesto”"))
        return super().button_confirm()

    # =========================
    #   DASHBOARD / RESUMEN
    # =========================
    def get_department_budget_data(self):
        BudgetLine = self.env['crossovered.budget.lines']
        AnalyticLine = self.env['account.analytic.line']
        today = fields.Date.context_today(self)

        departments = self.env['hr.department'].search([])

        result = []
        for dept in departments:
            accounts = self.env['account.analytic.account'].search([
                ('department_id', '=', dept.id),
                ('active', '=', True)
            ])
            if not accounts:
                continue

            total_budget = 0.0
            total_committed = 0.0
            for account in accounts:
                bline = BudgetLine.search([
                    ('analytic_account_id', '=', account.id),
                    ('date_from', '<=', today),
                    ('date_to', '>=', today),
                ], limit=1)
                if not bline:
                    continue

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

    @api.depends('order_line.analytic_distribution')
    def _compute_department_from_budget(self):
        """Calcular departamento automáticamente desde las líneas de presupuesto"""
        for order in self:
            department_totals = {}
            
            for line in order.order_line:
                if not line.analytic_distribution:
                    continue
                    
                analytic_dist = line.analytic_distribution
                
                # Convertir si es string
                if isinstance(analytic_dist, str):
                    try:
                        analytic_dist = json.loads(analytic_dist)
                    except:
                        continue
                
                if not isinstance(analytic_dist, dict):
                    continue
                
                for account_id_str, percentage in analytic_dist.items():
                    try:
                        account_id = int(account_id_str)
                        percentage_val = float(percentage)
                        
                        # Buscar líneas de presupuesto con esta cuenta analítica
                        budget_lines = self.env['crossovered.budget.lines'].search([
                            ('analytic_account_id', '=', account_id)
                        ])
                        
                        for budget_line in budget_lines:
                            if budget_line.department_id:
                                dept = budget_line.department_id
                                line_amount = line.price_total * (percentage_val / 100.0)
                                department_totals[dept.id] = department_totals.get(dept.id, 0.0) + line_amount
                                
                    except:
                        continue
            
            # Asignar departamento con mayor monto
            if department_totals:
                main_dept_id = max(department_totals, key=department_totals.get)
                order.department_id = main_dept_id
            else:
                order.department_id = False

    def action_recompute_all_departments(self):
        """Forzar recálculo de departamentos para todas las órdenes"""
        all_orders = self.search([])
        updated_count = 0
        
        for order in all_orders:
            old_dept = order.department_id
            order._compute_department_from_budget()
            
            if order.department_id != old_dept:
                updated_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Recálculo Completado',
                'message': f'Se actualizaron {updated_count} de {len(all_orders)} órdenes',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def cron_actualizar_departamentos(self):
        """Cron job para actualizar departamentos automáticamente"""
        try:
            # Buscar órdenes con distribución analítica
            orders_con_analitica = self.search([
                ('order_line.analytic_distribution', '!=', False)
            ])
            
            # Procesar órdenes
            actualizadas = 0
            for order in orders_con_analitica:
                depto_anterior = order.department_id
                order._compute_department_from_budget()
                
                if order.department_id != depto_anterior:
                    actualizadas += 1
            
            _logger.info(f"Cron departamentos: {actualizadas} órdenes actualizadas")
            
        except Exception as e:
            _logger.error(f"Error en cron de departamentos: {e}")