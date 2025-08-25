# models/pos_config.py
from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class PosConfig(models.Model):
    _inherit = "pos.config"

    # changes_product_id = fields.Many2one(
    #     "product.product",
    #     string="Producto para Cambios",
    #     compute="_compute_changes_product_id",
    #     compute_sudo=True,
    #     store=False,  # si quieres verlo siempre en el POS, no es necesario store=True
    # )


    @api.model
    def get_changes_product_id(self, config_id):
        cfg = self.browse(config_id).sudo()
        ICP = self.env["ir.config_parameter"].sudo().with_company(cfg.company_id)
        raw = (ICP.get_param("exchange.changes_product_id") or "").strip()
        pid = int(raw) if raw.isdigit() and int(raw) > 0 else 0
        return pid or False



    # @api.depends("company_id")
    # def _compute_changes_product_id(self):
    #     ICP = self.env["ir.config_parameter"].sudo()
    #     Product = self.env["product.product"].sudo()
    #     for cfg in self:
    #         val = False
    #         try:
    #             raw = (ICP.with_company(cfg.company_id)
    #                      .get_param("exchange.changes_product_id") or "").strip()
    #             if raw.isdigit():
    #                 prod = Product.browse(int(raw))
    #                 val = prod if prod.exists() else False
    #         except Exception:
    #             _logger.exception("compute changes_product_id cfg=%s", cfg.id)
    #         cfg.changes_product_id = val
