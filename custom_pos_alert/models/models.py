# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class custom_pos_alert(models.Model):
#     _name = 'custom_pos_alert.custom_pos_alert'
#     _description = 'custom_pos_alert.custom_pos_alert'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

