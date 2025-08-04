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

    def action_apply_discount(self):
        self.ensure_one()

        # Buscar o crear producto de descuento
        product = self.env['product.product'].search([('default_code', '=', 'DESC-GLOB')], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': 'Descuento Global',
                'default_code': 'DESC-GLOB',
                'type': 'service',
                'purchase_ok': True,
                'sale_ok': False,
            })

        # Calcular monto del descuento
        if self.discount_type == 'percentage':
            amount = -(self.order_id.amount_untaxed * self.discount_value / 100)
        else:
            amount = -abs(self.discount_value)

        # Verificar si ya existe un descuento en esta orden
        existing_discount = self.order_id.order_line.filtered(
            lambda l: l.product_id.default_code == 'DESC-GLOB'
        )

        if existing_discount:
            # Registrar mensaje en log
            _logger.info(
                f"Se intentó agregar un descuento global a la orden {self.order_id.name} "
                f"que ya contiene un descuento (ID línea: {existing_discount.id})"
            )
            raise UserError(
                "Esta orden ya tiene un descuento global aplicado. "
                "Puede eliminarlo directamente en las líneas para poder aplicar uno nuevo o actualizar el descuento."
            )

        # Crear línea de descuento
        self.env['purchase.order.line'].create({
            'order_id': self.order_id.id,
            'product_id': product.id,
            'name': f'Descuento Global ({self.discount_value}{"%" if self.discount_type == "percentage" else ""})',
            'product_qty': 1,
            'price_unit': amount,
            'discount_global_value': self.discount_value,
        })

        return {'type': 'ir.actions.act_window_close'}