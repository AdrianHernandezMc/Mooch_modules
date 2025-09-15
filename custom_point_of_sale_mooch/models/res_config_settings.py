from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    changes_product_id = fields.Many2one(
        "product.product",
        string="Producto para Cambios",
        help="Producto que se usará para operaciones de cambios/devolución."
    )

    loyalty_program_id = fields.Many2one(
        "loyalty.program",
        string="Programa vales",
        help="Programa configurable en settings",
        # Guarda/lee automáticamente en ir.config_parameter
        config_parameter="voucher.loyalty_program_id",
        company_dependent=True,
    )

    # Lee y guarda de forma manual en ir.config_parameter
    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        prod_id = ICP.get_param("exchange.changes_product_id")
        # _logger.info("DEBUG prod_id=%s (type=%s)", prod_id, type(prod_id).__name__)
        res.update(
            changes_product_id=int(prod_id) if prod_id and prod_id.isdigit() else False
            
        )
        # _logger.info("Resultado de producto=%s ", res)
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(
            "exchange.changes_product_id",
            str(self.changes_product_id.id or "")  # guarda vacío si no hay valor
        )

    