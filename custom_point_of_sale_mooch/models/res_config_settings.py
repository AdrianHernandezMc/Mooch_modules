# addons/exchange/models/res_config_settings.py
from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    changes_product_id = fields.Many2one(
        "product.product",
        string="Producto para Cambios",
        help="Producto que se usará para operaciones de cambios/devolución."
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        prod_id = ICP.get_param("exchange.changes_product_id")
        res.update(
            changes_product_id=int(prod_id) if prod_id and prod_id.isdigit() else False
        )
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(
            "exchange.changes_product_id",
            str(self.changes_product_id.id or "")  # guarda vacío si no hay valor
        )