# # -*- coding: utf-8 -*-
from odoo import models

class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_pos_payment_method(self):
        res = super()._loader_params_pos_payment_method()
        # añade el campo al payload que se manda al POS
        fields = res['search_params'].setdefault('fields', [])
        if 'require_transaction_id' not in fields:
            fields.append('require_transaction_id')
        return res



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

 