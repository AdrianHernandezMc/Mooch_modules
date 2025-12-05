# # -*- coding: utf-8 -*-
from odoo import models, api , _

class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_pos_payment_method(self):
        res = super()._loader_params_pos_payment_method()
        # añade el campo al payload que se manda al POS
        fields = res['search_params'].setdefault('fields', [])
        if 'require_transaction_id' not in fields:
            fields.append('require_transaction_id')
        return res



# class PosSession(models.Model):
#     _inherit = "pos.session"

#     def _loader_params_pos_config(self):
#         res = super()._loader_params_pos_config()
#         # fields_ = res["search_params"].setdefault("fields", [])
#         if "fields" in res["search_params"]:
#             fields_ = res["search_params"]["fields"]
#         else:
#             res["search_params"]["fields"] = []
#             fields_ = res["search_params"]["fields"]

#         if "changes_product_id" not in fields_:
#             fields_.append("changes_product_id")
#         return res
# -*- coding: utf-8 -*-
# models/pos_session_loader.py

class ReportSaleDetails(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'

    @api.model
    def get_sale_details(self, date_start=False, date_stop=False, config_ids=False, session_ids=False):
        # 1. Obtener datos originales
        data = super(ReportSaleDetails, self).get_sale_details(date_start, date_stop, config_ids, session_ids)
        
        # 2. Obtener sesión
        sessions = self.env['pos.session'].browse(session_ids)
        session_name = sessions[0].name if sessions else ''
        
        # 3. Consulta para conteos y deducciones
        all_lines = self.env['pos.order.line'].sudo().search([
            ('order_id.session_id', 'in', sessions.ids)
        ])

        # =========================================================
        # 4. TOTALES FORZADOS (LA VERDAD ES LO COBRADO)
        # =========================================================
        
        # A. SUMAR PAGOS (Esto es lo que realmente hay en caja)
        total_pagado_real = 0.0
        if 'payments' in data:
            for payment in data['payments']:
                total_pagado_real += payment['total']

        # B. CONTEO ARTÍCULOS
        total_items = sum(all_lines.mapped('qty'))

        # =========================================================
        # 5. DEDUCCIONES (Informativo)
        # =========================================================
        
        # Devoluciones
        refund_lines = all_lines.filtered(lambda l: l.qty < 0)
        dev_total = sum(abs(l.price_subtotal_incl) for l in refund_lines)
        
        # Descuentos
        disc_total = 0.0
        
        # Porcentaje
        percentage_disc_lines = all_lines.filtered(lambda l: l.qty > 0 and l.discount > 0)
        for l in percentage_disc_lines:
            if l.discount != 100:
                original_total = l.price_subtotal_incl / (1 - l.discount/100.0)
                disc_total += (original_total - l.price_subtotal_incl)
            else:
                taxes = l.tax_ids.compute_all(l.price_unit, l.order_id.pricelist_id.currency_id, l.qty, product=l.product_id, partner=l.order_id.partner_id)
                disc_total += taxes['total_included']

        # Descuento Global
        global_disc_lines = all_lines.filtered(lambda l: l.qty > 0 and l.price_unit < 0)
        disc_total += sum(abs(l.price_subtotal_incl) for l in global_disc_lines)

        deduction_total = dev_total + disc_total

        # =========================================================
        # 6. OTROS DATOS
        # =========================================================
        orders_count = len(sessions.mapped('order_ids'))
        
        # Limpieza nombres pago
        if 'payments' in data:
            for payment in data['payments']:
                original_name = payment['name']
                if session_name:
                    original_name = original_name.replace(session_name, '')
                payment['name'] = original_name.strip().strip('-').strip()

        # Movimientos Caja
        moves_info = []
        total_entradas = 0.0
        total_salidas = 0.0
        if sessions:
            domain = [('pos_session_id', 'in', sessions.ids)]
            lines = self.env['account.bank.statement.line'].sudo().search(domain)
            for line in lines:
                if not line.pos_payment_ids:
                    if line.amount > 0:
                        total_entradas += line.amount
                    else:
                        total_salidas += abs(line.amount)
                    moves_info.append({
                        'name': line.payment_ref or line.name or 'Movimiento',
                        'amount': line.amount,
                    })

        # 7. ACTUALIZAR DATOS
        data.update({
            'moves_info': moves_info,
            'summary_entradas': round(total_entradas, 2),
            'summary_salidas': round(total_salidas, 2),
            'session_name': session_name,
            'user_name': sessions[0].user_id.name if sessions else '',
            'orders_count': orders_count,
            
            # TOTALES
            'total_items': total_items,
            
            # AQUÍ ESTÁ EL ARREGLO:
            # En lugar de sumar productos, usamos la suma de PAGOS como total.
            'total_products_incl': round(total_pagado_real, 2), 
            
            # DEDUCCIONES
            'dev_total': round(dev_total, 2),
            'disc_total': round(disc_total, 2),
            'deduction_total': round(deduction_total, 2)
        })
        
        return data