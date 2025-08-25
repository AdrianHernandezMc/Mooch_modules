# # -*- coding: utf-8 -*-
# from odoo import models

# class PosSession(models.Model):
#     _inherit = "pos.session"

#     def _loader_params_pos_config(self):
#         res = super()._loader_params_pos_config()
#         # fields_ = res["search_params"].setdefault("fields", [])
#         if "fields" in res["search_params"]:
#             fields_ = res["search_params"]["fields"]
#         else:
#             res["search_params"]["fields"] = []
#             fields_ = res["search_params"]["fields"]

#         if "changes_product_id" not in fields_:
#             fields_.append("changes_product_id")
#         return res
# -*- coding: utf-8 -*-
# models/pos_session_loader.py
from odoo import models

class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_pos_config(self):
        res = super()._loader_params_pos_config()
        fields_ = res.setdefault("search_params", {}).setdefault("fields", [])
        if "changes_product_id" not in fields_:
            fields_.append("changes_product_id")
        return res
