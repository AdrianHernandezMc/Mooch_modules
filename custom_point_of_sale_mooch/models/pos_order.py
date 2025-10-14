from odoo import api, models, fields, _
from odoo.exceptions import UserError

# class PosOrder(models.Model):
#     _inherit = 'pos.order'

#     # @api.model
#     # def create_refund_coupon(self, order_id, product_codes, amount):
#     #     program = self.env['loyalty.program'].search([('name', '=', 'Reembolsos POS')], limit=1)
#     #     card = self.env['loyalty.card'].create({'program_id': program.id})
#     #     self.env['pos.loyalty.reference'].create({
#     #         'loyalty_card_id': card.id,
#     #         'order_id': order_id,
#     #         'product_codes': product_codes,
#     #     })
#     #     return card.id
#     # #-*- coding: utf-8 -*-
#     # from odoo import api, models

class PosOrder(models.Model):
    _inherit = 'pos.order'

#################Campos Adrian Muebles##############################
    delivery_contact_name = fields.Char("Nombre de contacto (entrega)")
    delivery_phone = fields.Char("Teléfono (entrega)")
    delivery_address = fields.Char("Dirección (entrega)")
    delivery_notes = fields.Text("Notas de entrega")
    delivery_geo_lat = fields.Float("Latitud (entrega)")
    delivery_geo_lng = fields.Float("Longitud (entrega)")
    delivery_maps_url = fields.Char("URL de Maps")

#################Fin de campos######################################

    @api.model
    def get_order_locations(self, order_ids):
        """
        Retorna para cada order_id un listado de diccionarios con:
            - product_id
            - producto
            - location_id
            - ubicacion_origen
        Utiliza únicamente el ORM de Odoo, sin consultas SQL directas.
        """
        # Carga las órdenes solicitadas
        orders = self.browse(order_ids)
        # Inicializa el resultado con listas vacías
        result = {order.id: [] for order in orders}

        # Mapea origin (nombre de orden) a order_id
        origin_map = {order.name: order.id for order in orders if order.name}
        #raise UserError(f"origin_map {origin_map}")
        #shop/0022;32
        if not origin_map:
            return result

        # Busca movimientos completados cuyas picking.origin coincida con una orden
        moves = self.env['stock.move'].search([
            ('state', '=', 'done'),
            ('picking_id.origin', 'in', list(origin_map.keys())),
        ])
    # Recorre los movimientos y agrupa los datos
        for move in moves:
            origin = move.picking_id.origin
            order_id = origin_map.get(origin)
            if not order_id:
                continue
            result[order_id].append({
                'product_id': move.product_id.id,
                'producto': move.product_id.product_tmpl_id.name,
                'code': move.product_id.product_tmpl_id.default_code,
                'location_id': move.location_id.id,
                'ubicacion_origen': move.location_id.name,
                'origin_id': move.location_dest_id.id,
            })
        return result
