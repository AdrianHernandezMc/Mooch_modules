from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class PurchaseBudgetWizard(models.TransientModel):
    _name = 'purchase.budget.wizard'
    _description = 'Wizard de Presupuesto para Órdenes de Compra'

    department_id = fields.Many2one(
        'hr.department', 
        string='Departamento', 
        required=True
    )
    password = fields.Char(
        string='Contraseña', 
        required=True,
        help='Contraseña para acceder al presupuesto del departamento',
        groups='base.group_system'
    )
    quarter = fields.Selection([
        ('Q1', 'Primer Trimestre (Ene-Mar)'),
        ('Q2', 'Segundo Trimestre (Abr-Jun)'),
        ('Q3', 'Tercer Trimestre (Jul-Sep)'),
        ('Q4', 'Cuarto Trimestre (Oct-Dic)'),
    ], string='Trimestre', required=True, default='Q1')
    
    # Campos calculados
    budget_lines = fields.Text(string='Detalles del Presupuesto', readonly=True)
    total_budget = fields.Float(string='Presupuesto Total', readonly=True)
    total_invoiced = fields.Float(string='Total Facturado', readonly=True)
    total_purchase_orders = fields.Float(string='Total Órdenes de Compra', readonly=True)
    total_available = fields.Float(string='Disponible', readonly=True)
    percentage_used = fields.Float(string='% Utilizado', readonly=True)
    budget_lines = fields.Html(string='Detalles del Presupuesto', readonly=True, sanitize=False)

    @api.model
    def _get_current_quarter(self):
        """Obtener el trimestre actual basado en la fecha"""
        today = fields.Date.today()
        month = today.month
        if month <= 3:
            return 'Q1'
        elif month <= 6:
            return 'Q2'
        elif month <= 9:
            return 'Q3'
        else:
            return 'Q4'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res['quarter'] = self._get_current_quarter()
        return res

    def _get_quarter_dates(self, quarter, year=None):
        """Obtener fechas de inicio y fin del trimestre"""
        if not year:
            year = fields.Date.today().year
        
        quarters = {
            'Q1': (f'{year}-01-01', f'{year}-03-31'),
            'Q2': (f'{year}-04-01', f'{year}-06-30'),
            'Q3': (f'{year}-07-01', f'{year}-09-30'),
            'Q4': (f'{year}-10-01', f'{year}-12-31'),
        }
        return quarters.get(quarter, (f'{year}-01-01', f'{year}-12-31'))

    def _validate_password(self, department):
        """Validar contraseña del departamento desde el campo configurado"""
        if not department.budget_password:
            raise ValidationError(_('Este departamento no tiene contraseña configurada'))
        
        if self.password != department.budget_password:
            raise ValidationError(_('Contraseña incorrecta para este departamento'))

    def action_process(self):
        """Procesar y mostrar el presupuesto"""
        self.ensure_one()
        
        try:
            # Validar contraseña
            self._validate_password(self.department_id)
            
            # Obtener datos del presupuesto
            budget_data = self._get_department_budget_data()
            
            # Calcular totales
            total_budget = sum(item['budget_total'] for item in budget_data)
            total_invoiced = sum(item['invoiced'] for item in budget_data)
            total_purchase_orders = sum(item['purchase_orders'] for item in budget_data)
            total_committed = total_invoiced + total_purchase_orders
            total_available = total_budget - total_committed
            
            # % Utilizado = Solo lo facturado actualmente / presupuesto total
            percentage_used = (total_invoiced / total_budget * 100) if total_budget > 0 else 0  # CAMBIADO
            
            # Actualizar campos
            self.write({
                'budget_lines': self._format_budget_lines(budget_data),
                'total_budget': total_budget,
                'total_invoiced': total_invoiced,
                'total_purchase_orders': total_purchase_orders,
                'total_available': total_available,
                'percentage_used': percentage_used,  # CAMBIADO: usar solo facturado
            })
            
            # Recargar el wizard
            return {
                'type': 'ir.actions.act_window',
                'name': 'Presupuesto',
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'views': [(False, 'form')],
            }
            
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error al calcular el presupuesto: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }

    def _get_department_budget_data(self):
        """Obtener datos de presupuesto del departamento"""
        BudgetLine = self.env['crossovered.budget.lines']
        
        year = fields.Date.today().year
        date_from, date_to = self._get_quarter_dates(self.quarter, year)
        
        # Buscar líneas de presupuesto del departamento
        budget_lines = BudgetLine.search([
            ('department_id', '=', self.department_id.id),
            ('date_from', '<=', date_to),
            ('date_to', '>=', date_from),
        ])
        
        if not budget_lines:
            return []
        
        result = []
        for bline in budget_lines:
            if not bline.analytic_account_id:
                continue

            # Monto ya facturado (usar valor absoluto)
            total_invoiced = abs(bline.practical_amount or 0)
            
            # Total de Órdenes de Compra (incluyendo RFQ y por aprobar)
            total_purchase_orders = self._get_total_purchase_orders(bline.analytic_account_id, date_from, date_to)
            
            # Total comprometido = facturado + órdenes de compra
            total_committed = total_invoiced + total_purchase_orders
            
            # Órdenes pendientes por facturar (para el detalle)
            pending_orders = self._get_pending_purchase_orders_detail(bline.analytic_account_id, date_from, date_to)
            
            # Disponible = Presupuesto - Total Comprometido
            available = bline.planned_amount - total_committed
            
            # % Utilizado = Solo lo facturado actualmente / presupuesto
            percentage_used = (total_invoiced / bline.planned_amount * 100) if bline.planned_amount > 0 else 0  # CAMBIADO
            
            result.append({
                'account': bline.analytic_account_id.name,
                'budget_total': bline.planned_amount,
                'invoiced': total_invoiced,
                'purchase_orders': total_purchase_orders,
                'total_committed': total_committed,
                'available': available,
                'percentage_used': percentage_used,  # CAMBIADO: usar solo facturado
                'pending_orders': pending_orders,
            })
        
        return result

    def _get_total_purchase_orders(self, analytic_account, date_from, date_to):
        """Obtener total de todas las Órdenes de Compra (incluyendo RFQ y por aprobar)"""
        PurchaseOrder = self.env['purchase.order']
        
        # Buscar TODAS las Órdenes de Compra (incluyendo RFQ - estados 'draft', 'sent', 'to approve', 'purchase')
        domain = [
            ('state', 'in', ['draft', 'sent', 'to approve', 'purchase']),  # Incluir RFQ y OCs confirmadas
            ('date_order', '>=', date_from),
            ('date_order', '<=', date_to),
        ]
        
        pos = PurchaseOrder.search(domain)
        total_po_amount = 0
        
        for po in pos:
            po_amount = 0
            for line in po.order_line:
                if line.analytic_distribution:
                    analytic_dist = line.analytic_distribution
                    if isinstance(analytic_dist, str):
                        import json
                        try:
                            analytic_dist = json.loads(analytic_dist)
                        except json.JSONDecodeError:
                            continue
                    
                    if str(analytic_account.id) in analytic_dist:
                        percentage = float(analytic_dist[str(analytic_account.id)]) / 100.0
                        po_amount += abs(line.price_total) * percentage
            
            total_po_amount += po_amount
        
        return total_po_amount

    def _get_pending_purchase_orders_detail(self, analytic_account, date_from, date_to):
        """Obtener detalle de órdenes de compra (incluyendo por aprobar)"""
        PurchaseOrder = self.env['purchase.order']
        
        domain = [
            ('state', 'in', ['draft', 'sent', 'to approve', 'purchase']),  # Incluir todos los estados pendientes
            ('date_order', '>=', date_from),
            ('date_order', '<=', date_to),
        ]
        
        pos = PurchaseOrder.search(domain)
        pending_orders = []
        
        for po in pos:
            po_amount = 0
            for line in po.order_line:
                if line.analytic_distribution:
                    analytic_dist = line.analytic_distribution
                    if isinstance(analytic_dist, str):
                        import json
                        try:
                            analytic_dist = json.loads(analytic_dist)
                        except json.JSONDecodeError:
                            continue
                    
                    if str(analytic_account.id) in analytic_dist:
                        percentage = float(analytic_dist[str(analytic_account.id)]) / 100.0
                        po_amount += abs(line.price_total) * percentage
            
            if po_amount > 0:
                # Determinar el concepto según el estado
                if po.state == 'draft':
                    concept = 'Solicitud de Cotización (Borrador)'
                elif po.state == 'sent':
                    concept = 'Solicitud de Cotización (Enviada)'
                elif po.state == 'to approve':
                    concept = 'Pendiente por Aprobar'
                elif po.state == 'purchase':
                    concept = 'Confirmada - Pendiente por Facturar'
                else:
                    concept = 'Previo Presupuestado'
                
                pending_orders.append({
                    'name': po.name,
                    'partner': po.partner_id.name,
                    'amount': po_amount,
                    'state': po.state,
                    'concept': concept
                })
        
        return pending_orders

    def _format_budget_lines(self, budget_data):
        """Formatear los datos del presupuesto para mostrar en HTML compacto"""
        if not budget_data:
            return "<p>No se encontraron datos de presupuesto para este departamento/trimestre.</p>"
        
        html_parts = []
        
        for item in budget_data:
            # Encabezado de la cuenta
            html_parts.append(f"<div style='margin-bottom: 15px;'>")
            html_parts.append(f"<h4 style='color: #0d6efd; margin-bottom: 10px;'>{item['account']}</h4>")
            
            # Resumen compacto
            html_parts.append("""
            <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 15px; font-size: 16px;'>
                <div><strong>Presupuesto Total:</strong><br>${:,.2f}</div>
                <div><strong>Facturado Total:</strong><br>${:,.2f}</div>
                <div><strong>Órdenes Pendientes:</strong><br>${:,.2f}</div>
                <div><strong>Comprometido Con Ordenes:</strong><br>${:,.2f}</div>
                <div><strong>Disponible Total:</strong><br>${:,.2f}</div>
                <div><strong>% Utilizado:</strong><br>{:.1f}%</div>
            </div>
            """.format(
                item['budget_total'],
                item['invoiced'],
                item['purchase_orders'],
                item['total_committed'],
                item['available'],
                item['percentage_used']
            ))
            
            # Tabla de órdenes pendientes
            if item['pending_orders']:
                html_parts.append("<h5 style='margin: 15px 0 8px 0; font-size: 14px;'>Órdenes de Compra Pendientes:</h5>")
                html_parts.append("""
                <div style='overflow-x: auto;'>
                <table style='width: 100%; border-collapse: collapse; font-size: 16px; min-width: 600px;'>
                    <thead>
                        <tr style='background-color: #e9ecef;'>
                            <th style='border: 1px solid #dee2e6; padding: 6px; text-align: left;'>Referencia De Orden</th>
                            <th style='border: 1px solid #dee2e6; padding: 6px; text-align: left;'>Proveedor</th>
                            <th style='border: 1px solid #dee2e6; padding: 6px; text-align: right;'>Monto</th>
                            <th style='border: 1px solid #dee2e6; padding: 6px; text-align: left;'>Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                """)
                
                for order in item['pending_orders']:
                    html_parts.append("""
                    <tr>
                        <td style='border: 1px solid #dee2e6; padding: 6px; font-size: 15px;'>{}</td>
                        <td style='border: 1px solid #dee2e6; padding: 6px; font-size: 15px;'>{}</td>
                        <td style='border: 1px solid #dee2e6; padding: 6px; text-align: right; font-size: 15px;'>${:,.2f}</td>
                        <td style='border: 1px solid #dee2e6; padding: 6px; font-size: 15px;'>{}</td>
                    </tr>
                    """.format(
                        order['name'],
                        order['partner'],
                        order['amount'],
                        order['concept']
                    ))
                
                html_parts.append("</tbody></table></div>")
            
            html_parts.append("</div>")
        
        return "".join(html_parts)
    
    def action_cancel(self):
        """Cancelar el wizard"""
        return {'type': 'ir.actions.act_window_close'}