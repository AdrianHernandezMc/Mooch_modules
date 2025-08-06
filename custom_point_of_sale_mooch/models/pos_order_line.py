from odoo import models, api, fields,_
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    @api.model
    def _loader_params_pos_order_line(self):
        params = super()._loader_params_pos_order_line()
        params["search_params"]["fields"].extend(["changes"])
        _logger.info(f"Result Python: {params}")
        return params


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    changes = fields.Float(
        string="Changes",
        digits="Product Unit of Measure",
        default=0.0,
    )


    @api.model
    def _export_for_ui(self, line):
        res = super()._export_for_ui(line)
        res["changes"] = line.changes
        _logger.info(f"Result Python: {res}")
        return res


    @api.model
    def action_simple_refund(self, line_ids, qtys):
        """
        line_ids: lista de IDs de líneas
        qtys:     lista de cantidades a devolver (positivas) : changes
        """
        if len(line_ids) != len(qtys):
            raise ValidationError(_("IDs y cantidades deben tener la misma longitud."))

        for line, qty in zip(self.browse(line_ids), qtys):
            if qty <= 0:
                continue

            # 1) Validación básica
            if qty > (line.qty - line.refunded_qty):
                raise ValidationError(
                    _("La cantidad  (%s) a devolver excede  qty(%s),refund(%s) lo vendido en la línea %s.")
                    % (qty,line.qty, - line.refunded_qty, line.display_name)
                )

            # 2) Actualiza refunded_qty
            line.refunded_qty += qty
            #_logger.info("Linea %s ➜ refunded_qty += %s", line.id, qty)

            # 3) (Opcional) genera un picking de entrada
            # Aquí pondrías tu lógica de stock si la necesitas
            # self._generate_simple_return_picking(line, qty)
        return True


class PosChanges(models.Model):
    _name = "pos.changes"
    _description = "Cambios entre pedidos del Punto de Venta"
    _rec_name = "origin_reference"

    origin_id = fields.Many2one(
        'pos.order',
        string="Pedido Origen",
        required=True,
        ondelete='cascade',
    )
    dest_order_uid = fields.Char(
        string="UID Pedido Destino (frontend)",
        help="UID de la orden en el cliente POS, antes de validar la venta.",
        readonly=True,
    )
    dest_id = fields.Many2one(
        'pos.order',
        string="Pedido Destino",
        ondelete='cascade',
        help="Se completa tras validar la venta y crear el pedido en DB."
    )
    product_id = fields.Many2one(
        'product.product',
        string="Producto",
        required=True,
        ondelete='restrict'
    )

    origin_reference = fields.Char(
        related="origin_id.pos_reference",
        string="Ref. Origen",
        store=True,
        readonly=True,
    )
    destination_reference = fields.Char(
        related="dest_id.pos_reference",
        string="Ref. Destino",
        store=True,
        readonly=True,
    )
    product_name = fields.Char(
        related="product_id.name",
        string="Nombre Producto",
        store=True,
        readonly=True,
    )
    default_code = fields.Char(
        related="product_id.default_code",
        string="Código Interno",
        store=True,
        readonly=True,
    )

    @api.model
    def poschanges_links_pre(self, origin_id, dest_order_uid, product_ids):
        _logger.info("▶▶ poschanges_links_pre called with origin=%s dest_uid=%s products=%s",
                     origin_id, dest_order_uid, product_ids)
        """
        Crea registros en pos.changes antes de validar la venta,
        guardando el UID temporal y el producto por línea.
        :param origin_id: ID del pedido POS origen
        :param dest_order_uid: UID temporal de la orden destino en el cliente
        :param product_ids: lista de product.product IDs
        :return: lista de IDs de pos.changes creados
        """
        origin = self.env['pos.order'].browse(origin_id)
        if not origin:
            raise ValidationError("Pedido origen inválido.")
        created = []
        for pid in product_ids:
            rec = self.create({
                'origin_id':     origin.id,
                'dest_order_uid': dest_order_uid,
                'product_id':    pid,
            })
            created.append(rec.id)
            _logger.info("◀◀ poschanges_links_pre created IDs %s", created)
        return created

# ------------------------------------------------------------------
# Hook en pos.order para completar dest_id tras la creación real
# ------------------------------------------------------------------
class PosOrder(models.Model):
    _inherit = "pos.order"

    def _process_order(self, order, draft=False, existing_order=None):
        # 1) Deja que Odoo cree la orden y te devuelva su ID
        order_id = super()._process_order(order, draft=draft, existing_order=existing_order)
        # 2) Aquí puedes vincular tu pos.changes
        uid = order.get('data', {}).get('uid')
        if uid:
            changes = self.env['pos.changes'].search([('dest_order_uid','=', uid)])
            if changes:
                changes.write({
                    'dest_id': order_id,
                    'dest_order_uid': False,
                })
        return order_id

    # @api.model_create_multi
    # def create(self, vals_list):
    #     orders = super().create(vals_list)
    #     for order in orders:
    #         # Busca todos los PosChanges hechos con el UID de este pedido
    #         changes = self.env['pos.changes'].search([
    #             ('dest_order_uid', '=', order.pos_reference)
    #         ])

    #         if changes:
    #             # Escribe el dest_id real y limpia el UID temporal
    #             changes.write({
    #                 'dest_id': order.id,
    #                 'dest_order_uid': False,
    #             })
    #     return orders



    # @api.model
    # def _export_for_ui(self):
    #     original = super(PosOrderLine, self).export_for_ui()
    #     results = []
    #     for data, line in zip(original, self):
    #         data['changes'] = line.changes
    #         results.append(data)
    #         _logger.info(f"Result Python: {results}")
    #     return results




