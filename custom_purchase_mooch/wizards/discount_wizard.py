from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PurchaseDiscountWizard(models.TransientModel):
    _name = 'purchase.discount.wizard'
    _description = 'Asistente para descuento global'

    discount_type = fields.Selection([
        ('percentage', 'Porcentaje'),
        ('fixed', 'Monto fijo')],
        string='Tipo de descuento',
        default='percentage')

    discount_value = fields.Float('Valor del descuento', required=True)
    order_id = fields.Many2one('purchase.order', required=True)

    @api.constrains('discount_value')
    def _check_discount_limit(self):
        for record in self:
            if record.discount_type == 'percentage' and record.discount_value > 100:
                raise UserError("El descuento no puede ser mayor al 100%")
            elif record.discount_type == 'fixed' and record.discount_value > record.order_id.amount_untaxed:
                raise UserError("El descuento no puede ser mayor al monto total de la orden")

    def _get_or_create_analytic_account(self):
        """Obtiene o crea la cuenta analítica para descuentos globales"""
        account = self.env['account.analytic.account'].search([
            ('code', '=', 'DESC-GLOB'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not account:
            analytic_plan = self.env['account.analytic.plan'].search([], limit=1)
            if not analytic_plan:
                raise UserError(
                    "No se encontró ningún plan analítico configurado. "
                    "Por favor configure uno en Contabilidad > Configuración > Planes Analíticos."
                )
            
            account = self.env['account.analytic.account'].create({
                'name': 'Descuentos Globales',
                'code': 'DESC-GLOB',
                'plan_id': analytic_plan.id,
                'company_id': self.env.company.id,
                'active': True,
            })
            _logger.info(f"Cuenta analítica creada para descuentos globales (ID: {account.id})")
        
        return account

    def action_apply_discount(self):
        self.ensure_one()
        
        # Validar límite del descuento (código existente)
        if self.discount_type == 'percentage' and self.discount_value > 100:
            raise UserError("El descuento porcentual no puede ser mayor al 100%")
        elif self.discount_type == 'fixed' and self.discount_value > self.order_id.amount_untaxed:
            raise UserError("El descuento en monto fijo no puede superar el total de la orden")

        # Buscar o crear producto de descuento (código existente)
        product = self.env['product.product'].search([('default_code', '=', 'DESC-GLOB')], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': 'Descuento Global',
                'default_code': 'DESC-GLOB',
                'type': 'service',
                'purchase_ok': True,
                'sale_ok': False,
            })

        # ===== CAMBIO PRINCIPAL =====
        # Obtener cuenta analítica de la primera línea de producto
        analytic_distribution = {}
        if self.order_id.order_line:
            first_product_line = self.order_id.order_line.filtered(
                lambda l: l.product_id.default_code != 'DESC-GLOB'
            )[:1]
            
            if first_product_line and first_product_line.analytic_distribution:
                if isinstance(first_product_line.analytic_distribution, str):
                    try:
                        analytic_distribution = json.loads(first_product_line.analytic_distribution)
                    except json.JSONDecodeError:
                        analytic_distribution = {}
                elif isinstance(first_product_line.analytic_distribution, dict):
                    analytic_distribution = first_product_line.analytic_distribution.copy()
        
        # Si no encontramos distribución, usamos la cuenta por defecto
        if not analytic_distribution:
            analytic_account = self._get_or_create_analytic_account()
            analytic_distribution = {str(analytic_account.id): 100}
        # ===== FIN DEL CAMBIO =====

        # Calcular monto del descuento (código existente)
        if self.discount_type == 'percentage':
            amount = -(self.order_id.amount_untaxed * self.discount_value / 100)
        else:
            amount = -abs(self.discount_value)

        # Verificar si ya existe un descuento en esta orden (código existente)
        existing_discount = self.order_id.order_line.filtered(
            lambda l: l.product_id.default_code == 'DESC-GLOB'
        )

        if existing_discount:
            _logger.info(f"Intento de duplicar descuento en orden {self.order_id.name}")
            raise UserError("Ya existe un descuento global en esta orden. Elimínelo primero para aplicar uno nuevo.")

        # Crear línea de descuento (solo cambia analytic_distribution)
        self.env['purchase.order.line'].create({
            'order_id': self.order_id.id,
            'product_id': product.id,
            'name': f'Descuento Global ({self.discount_value}{"%" if self.discount_type == "percentage" else ""})',
            'product_qty': 1,
            'price_unit': amount,
            'discount_global_value': self.discount_value,
            'analytic_distribution': analytic_distribution,  # Usamos la distribución calculada
        })

        # Retorno existente
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Descuento aplicado',
                'message': f'Descuento global de {self.discount_value}{"%" if self.discount_type == "percentage" else ""} aplicado correctamente',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }