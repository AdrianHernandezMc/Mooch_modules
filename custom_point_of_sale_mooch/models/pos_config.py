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
    advanced_employee_ids = fields.Many2many(
        'hr.employee',
        string='Advanced Employees'
    )

#################Campos Adrian Muebles##############################
    is_home_box = fields.Boolean(
        string="¿Es caja de Hogar?",
        help="Activa comportamientos especiales para cajas de Muebles/Hogar. "
             "Cuando esté habilitado podrás capturar datos de pedido del cliente "
             "para impresión de documentos de entrega."
    )
    enable_maps = fields.Boolean(
        string="Habilitar Google Maps en POS",
        help="Muestra preview de Google Maps en el popup si hay API Key."
    )
    google_maps_api_key = fields.Char(
        string="Google Maps API Key",
        help="API Key para Google Maps Embed/Places. (Opcional)"
    )
#################Fin de camgps######################################


    @api.model
    def get_changes_product_id(self, config_id):
        cfg = self.browse(config_id).sudo()
        ICP = self.env["ir.config_parameter"].sudo().with_company(cfg.company_id)
        raw = (ICP.get_param("exchange.changes_product_id") or "").strip()
        pid = int(raw) if raw.isdigit() and int(raw) > 0 else 0
        return pid or False


    @api.model
    def get_loyalty_program_id(self, config_id):
        cfg = self.browse(config_id).sudo()
        ICP = self.env["ir.config_parameter"].sudo().with_company(cfg.company_id)
        raw = (ICP.get_param("voucher.loyalty_program_id") or "").strip()
        pid = int(raw) if raw.isdigit() and int(raw) > 0 else 0
        return pid or False


    @api.model
    def get_withdrawal(self, config_id=None):
        ICP = self.env["ir.config_parameter"].sudo()
        if config_id:
            cfg = self.browse(config_id)
            if cfg and cfg.company_id:
                ICP = ICP.with_company(cfg.company_id.id)
        val = ICP.get_param("point_of_sale.pos_withdrawal_amount")
        try:
            return float(val or 0.0)
        except Exception:
            return 0.0
        
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




