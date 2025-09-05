# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class PurchaseDiscountWizard(models.TransientModel):
    _name = 'purchase.discount.wizard'
    _description = 'Asistente para descuento global'

    discount_type = fields.Selection(
        [('percentage', 'Porcentaje'), ('fixed', 'Monto fijo')],
        string='Tipo de descuento',
        default='percentage'
    )
    discount_value = fields.Float('Valor del descuento', required=True)

    # NO required: ahora puede venir de OC o de Factura
    order_id = fields.Many2one('purchase.order', string='Orden de compra')
    move_id  = fields.Many2one('account.move', string='Factura proveedor')

    # ---------- Defaults según desde dónde se abre ----------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'order_id' in self._fields and not res.get('order_id'):
            def_order = self.env.context.get('default_order_id')
            if def_order:
                res['order_id'] = def_order
        if 'move_id' in self._fields and not res.get('move_id'):
            def_move = self.env.context.get('default_move_id')
            if def_move:
                res['move_id'] = def_move

        if not res.get('order_id') and not res.get('move_id'):
            active_model = self.env.context.get('active_model')
            active_id = self.env.context.get('active_id')
            if active_model == 'purchase.order' and active_id:
                res['order_id'] = active_id
            elif active_model == 'account.move' and active_id:
                res['move_id'] = active_id
        return res

    # ---------- Validaciones ----------
    @api.constrains('discount_value', 'discount_type', 'order_id', 'move_id')
    def _check_discount_limit(self):
        for w in self:
            if w.discount_type == 'percentage' and w.discount_value > 100:
                raise UserError("El descuento no puede ser mayor al 100%.")
            base = 0.0
            if w.order_id:
                base = w.order_id.amount_untaxed
            elif w.move_id:
                base = w.move_id.amount_untaxed
            if w.discount_type == 'fixed' and base and w.discount_value > base:
                raise UserError("El descuento no puede ser mayor al monto total (antes de impuestos).")
            if not w.order_id and not w.move_id:
                raise UserError("Debes seleccionar una Orden de compra o una Factura.")
            if w.order_id and w.move_id:
                raise UserError("Selecciona solo una: Orden de compra o Factura, no ambas.")

    # ---------- Utilidades ----------
    def _get_or_create_analytic_account(self):
        Analytic = self.env['account.analytic.account'].sudo()
        account = Analytic.search([
            ('code', '=', 'DESC-GLOB'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        if not account:
            plan = self.env['account.analytic.plan'].sudo().search([], limit=1)
            if not plan:
                raise UserError(
                    "No se encontró ningún plan analítico configurado.\n"
                    "Configura uno en Contabilidad > Configuración > Planes Analíticos."
                )
            account = Analytic.create({
                'name': 'Descuentos Globales',
                'code': 'DESC-GLOB',
                'plan_id': plan.id,
                'company_id': self.env.company.id,
                'active': True,
            })
            _logger.info("Cuenta analítica creada para descuentos globales (ID: %s)", account.id)
        return account

    def _get_discount_product(self):
        Prod = self.env['product.product'].sudo()
        product = Prod.search([('default_code', '=', 'DESC-GLOB')], limit=1)
        if not product:
            product = Prod.create({
                'name': 'Descuento Global',
                'default_code': 'DESC-GLOB',
                'type': 'service',
                'purchase_ok': True,
                'sale_ok': False,
            })
        return product

    def _compute_amount(self, base_amount):
        if self.discount_type == 'percentage':
            return -(base_amount * (self.discount_value or 0.0) / 100.0)
        else:
            return -abs(self.discount_value or 0.0)

    def _find_first_distribution(self, distribution):
        if not distribution:
            return {}
        if isinstance(distribution, dict):
            return distribution.copy()
        if isinstance(distribution, str):
            try:
                return json.loads(distribution) or {}
            except json.JSONDecodeError:
                return {}
        return {}

    def _recompute_move_totals(self, move):
        """Compatibilidad entre builds: fuerza recálculo si existe."""
        if hasattr(move, '_recompute_dynamic_lines'):
            return move._recompute_dynamic_lines(recompute_all_taxes=True)
        if hasattr(move, '_recompute_tax_lines'):
            return move._recompute_tax_lines()
        if hasattr(move, '_compute_amount'):
            return move._compute_amount()
        return True

    # ---------- Acción principal ----------
    def action_apply_discount(self):
        self.ensure_one()
        product = self._get_discount_product()

        # ===== Orden de Compra =====
        if self.order_id:
            po = self.order_id
            existing_discount = po.order_line.filtered(lambda l: l.product_id.default_code == 'DESC-GLOB')
            if existing_discount:
                raise UserError("Ya existe un descuento global en esta orden. Elimínalo primero para aplicar uno nuevo.")

            analytic_distribution = {}
            first_line = po.order_line.filtered(lambda l: l.product_id.default_code != 'DESC-GLOB')[:1]
            if first_line:
                analytic_distribution = self._find_first_distribution(first_line.analytic_distribution)
            if not analytic_distribution:
                analytic_distribution = {str(self._get_or_create_analytic_account().id): 100}

            amount = self._compute_amount(po.amount_untaxed)

            pol_vals = {
                'order_id': po.id,
                'product_id': product.id,
                'name': f'Descuento Global ({self.discount_value}{"%" if self.discount_type == "percentage" else ""})',
                'product_qty': 1,
                'price_unit': amount,
                'analytic_distribution': analytic_distribution,
            }
            if 'discount_global_value' in self.env['purchase.order.line']._fields:
                pol_vals['discount_global_value'] = self.discount_value

            self.env['purchase.order.line'].create(pol_vals)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Descuento aplicado',
                    'message': f'Descuento global de {self.discount_value}'
                               f'{"%" if self.discount_type == "percentage" else ""} aplicado a la Orden.',
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

        # ===== Factura Proveedor =====
        if self.move_id:
            move = self.move_id
            if move.move_type not in ('in_invoice', 'in_refund'):
                raise UserError("Este asistente solo se puede usar en facturas de proveedor o reembolsos.")

            existing_discount = move.invoice_line_ids.filtered(lambda l: l.product_id.default_code == 'DESC-GLOB')
            if existing_discount:
                raise UserError("Ya existe un descuento global en esta factura. Elimínalo primero para aplicar uno nuevo.")

            analytic_distribution = {}
            first_inv_line = move.invoice_line_ids.filtered(lambda l: l.product_id.default_code != 'DESC-GLOB')[:1]
            if first_inv_line:
                analytic_distribution = self._find_first_distribution(first_inv_line.analytic_distribution)
            if not analytic_distribution:
                analytic_distribution = {str(self._get_or_create_analytic_account().id): 100}

            amount = self._compute_amount(move.amount_untaxed)

            line_vals = {
                'move_id': move.id,
                'product_id': product.id,
                'name': f'Descuento Global ({self.discount_value}{"%" if self.discount_type == "percentage" else ""})',
                'quantity': 1,
                'price_unit': amount,  # negativo
            }
            # Solo si el campo existe en tu build
            if 'analytic_distribution' in self.env['account.move.line']._fields:
                line_vals['analytic_distribution'] = analytic_distribution

            self.env['account.move.line'].create(line_vals)

            # Recalcular totales (compat)
            self._recompute_move_totals(move)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Descuento aplicado',
                    'message': f'Descuento global de {self.discount_value}'
                               f'{"%" if self.discount_type == "percentage" else ""} aplicado a la Factura.',
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

        return {'type': 'ir.actions.act_window_close'}
