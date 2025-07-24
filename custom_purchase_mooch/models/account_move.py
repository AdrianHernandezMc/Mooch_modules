# addons/purchase_picking_docs/models/account_move.py
from odoo import api, fields, models

class AccountMove(models.Model):
    _inherit = 'account.move'

    purchase_id = fields.Many2one(
        'purchase.order', string='Purchase Order', copy=False, readonly=True,
        compute='_compute_purchase_id', store=True
    )

    @api.depends('invoice_origin')
    def _compute_purchase_id(self):
        for move in self:
            if move.move_type == 'in_invoice' and move.invoice_origin:
                po = self.env['purchase.order'].search(
                    [('name', '=', move.invoice_origin)], limit=1
                )
                move.purchase_id = po
            else:
                move.purchase_id = False

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            if move.purchase_id:
                po_atts = self.env['ir.attachment'].search([
                    ('res_model', '=', 'purchase.order'),
                    ('res_id', '=', move.purchase_id.id),
                ])
                for att in po_atts:
                    # sustituimos datas_fname por name
                    exists = self.env['ir.attachment'].search([
                        ('res_model', '=', 'account.move'),
                        ('res_id', '=', move.id),
                        ('name', '=', att.name),
                    ], limit=1)
                    if not exists:
                        att.copy({
                            'res_model': 'account.move',
                            'res_id': move.id,
                        })
        return moves

    def write(self, vals):
        res = super().write(vals)
        if 'invoice_origin' in vals:
            for move in self:
                if move.purchase_id:
                    po_atts = self.env['ir.attachment'].search([
                        ('res_model', '=', 'purchase.order'),
                        ('res_id', '=', move.purchase_id.id),
                    ])
                    for att in po_atts:
                        exists = self.env['ir.attachment'].search([
                            ('res_model', '=', 'account.move'),
                            ('res_id', '=', move.id),
                            ('name', '=', att.name),
                        ], limit=1)
                        if not exists:
                            att.copy({
                                'res_model': 'account.move',
                                'res_id': move.id,
                            })
        return res
