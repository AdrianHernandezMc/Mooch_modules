# custom_credit_mooch/models/res_partner.py
from odoo import models, fields, api
from datetime import date
import math

class ResPartner(models.Model):
    _inherit = 'res.partner'

    credit_limit = fields.Monetary(
        string="Límite de Crédito",
        related='limcred_mooch',
        help="Límite máximo de crédito asignado al cliente",
        store=False,
        currency_field='currency_id',
    )
    credit_balance = fields.Monetary(
        string="Saldo de Crédito",
        compute='_compute_credit_balance',
        readonly=True,
        help="Suma de los importes pendientes de facturas",
    )
    credit_available = fields.Monetary(
        string="Crédito Disponible",
        compute='_compute_credit_balance',
        readonly=True,
        help="Límite menos el saldo pendiente",
    )

    credit_age_months = fields.Integer(
        string="Meses de Crédito",
        compute='_compute_credit_dates',
        readonly=True,
    )
    credit_next_due = fields.Date(
        string="Próximo a Vencer",
        compute='_compute_credit_dates',
        readonly=True,
    )

    @api.depends('invoice_ids.amount_residual', 'invoice_ids.state')
    def _compute_credit_balance(self):
        for partner in self:
            # facturas posteadas de cliente con importe residual > 0
            invs = partner.invoice_ids.filtered(
                lambda inv: inv.state == 'posted' and
                            inv.move_type == 'out_invoice' and
                            inv.amount_residual > 0
            )
            balance = sum(invs.mapped('amount_residual'))
            partner.credit_balance = balance
            partner.credit_available = partner.credit_limit - balance

    @api.depends('invoice_ids.invoice_date', 'invoice_ids.invoice_date_due',
                 'invoice_ids.amount_residual', 'invoice_ids.state')
    def _compute_credit_dates(self):
        today = date.today()
        for partner in self:
            invs = partner.invoice_ids.filtered(
                lambda inv: inv.state == 'posted' and inv.amount_residual > 0
            )
            if not invs:
                partner.credit_age_months = 0
                partner.credit_next_due = False
                continue
            future_dues = invs.filtered(lambda inv: inv.invoice_date_due and inv.invoice_date_due >= today)
            partner.credit_next_due = (min(future_dues.mapped('invoice_date_due'))
                                       if future_dues else
                                       min(invs.mapped('invoice_date_due')))
            oldest = min((inv.invoice_date for inv in invs if inv.invoice_date), default=today)
            days = (today - oldest).days
            partner.credit_age_months = math.ceil(days / 30)
