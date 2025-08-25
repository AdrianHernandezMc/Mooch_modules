from odoo import models, fields, api

class StockPickingPurchaseTotals(models.Model):
    _inherit = 'stock.picking'

    # Moneda de la OC (si existe). Usamos related para que siempre muestre la moneda correcta.
    po_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda OC',
        related='purchase_id.currency_id',
        readonly=True,
        store=True,
    )

    # Totales de la OC (relacionados directamente)
    po_amount_untaxed = fields.Monetary(
        string='OC Subtotal',
        currency_field='po_currency_id',
        related='purchase_id.amount_untaxed',
        readonly=True,
        store=True,
    )
    po_amount_tax = fields.Monetary(
        string='OC Impuestos',
        currency_field='po_currency_id',
        related='purchase_id.amount_tax',
        readonly=True,
        store=True,
    )
    po_amount_total = fields.Monetary(
        string='OC Total',
        currency_field='po_currency_id',
        related='purchase_id.amount_total',
        readonly=True,
        store=True,
    )

    # Costo de este traslado valorado con precios/impuestos de la OC (opcional)
    po_picking_amount_untaxed = fields.Monetary(
        string='Costo de este traslado (s/imp)',
        currency_field='po_currency_id',
        compute='_compute_po_picking_amounts',
        store=False,
        readonly=True,
    )
    po_picking_amount_tax = fields.Monetary(
        string='Costo de este traslado (Impuesto)',
        currency_field='po_currency_id',
        compute='_compute_po_picking_amounts',
        store=False,
        readonly=True,
    )
    po_picking_amount_total = fields.Monetary(
        string='Costo de este traslado (c/imp)',
        currency_field='po_currency_id',
        compute='_compute_po_picking_amounts',
        store=False,
        readonly=True,
    )

    @api.onchange(
        'purchase_id', 'purchase_id.currency_id', 'purchase_id.partner_id',
        'move_ids.state', 'move_ids.quantity', 'move_ids.product_uom',
        'move_ids.purchase_line_id.price_unit', 'move_ids.purchase_line_id.taxes_id',
        'move_line_ids.qty_done', 'move_line_ids.product_uom_id',
        'state'
    )
    def _compute_po_picking_amounts(self):
        """Valúa únicamente lo movido en este picking con los precios/impuestos de la OC.
           Usa el enlace nativo move.purchase_line_id de purchase_stock.
        """
        for picking in self:
            untaxed = 0.0
            total = 0.0
            po = picking.purchase_id
            if not po:
                picking.po_picking_amount_untaxed = 0.0
                picking.po_picking_amount_tax = 0.0
                picking.po_picking_amount_total = 0.0
                continue

            currency = po.currency_id
            partner = po.partner_id

            for mv in picking.move_ids.filtered(lambda m: m.state != 'cancel'):
                pol = mv.purchase_line_id
                if not pol:
                    # Si el move no viene de una línea de compra, lo omitimos
                    continue

                # Cantidad real movida; si no hay done todavía, tomamos la esperada del move
                qty_done = sum(mv.move_line_ids.filtered(lambda l: l.state != 'cancel').mapped('qty_done')) or 0.0
                qty = qty_done if qty_done > 0.0 else (mv.quantity or 0.0)

                if qty <= 0.0:
                    continue

                # Convertimos a la UoM de la línea de compra para que el price_unit sea coherente
                uom_src = mv.product_uom
                uom_po = pol.product_uom or uom_src
                if uom_src and uom_po and uom_src != uom_po:
                    qty = uom_src._compute_quantity(qty, uom_po)

                price_unit = pol.price_unit  # por defecto s/imp; si tienes descuento custom, ajusta aquí
                taxes = pol.taxes_id

                if taxes:
                    res = taxes.compute_all(
                        price_unit,
                        currency,
                        qty,
                        product=mv.product_id,
                        partner=partner,
                    )
                    untaxed += res.get('total_excluded', price_unit * qty)
                    total   += res.get('total_included', price_unit * qty)
                else:
                    line_total = price_unit * qty
                    untaxed += line_total
                    total   += line_total

            tax = total - untaxed

            picking.po_picking_amount_untaxed = currency.round(untaxed) if currency else untaxed
            picking.po_picking_amount_tax = currency.round(tax) if currency else tax
            picking.po_picking_amount_total   = currency.round(total)   if currency else total
