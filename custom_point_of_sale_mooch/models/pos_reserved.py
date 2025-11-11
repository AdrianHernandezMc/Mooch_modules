# -*- coding: utf-8 -*-
from odoo import api, fields, models

class PosReserved(models.Model):
    _name = "pos.reserved"
    _description = "POS Apartados / Reservados"
    _rec_name = "name"   # campo usado como display_name

    # Campos base
    user_id = fields.Many2one("res.users", string="Usuario")
    company_id = fields.Many2one("res.company", string="Compañía")
    # sequence_number = fields.Integer(string="Número de secuencia")
    session_id = fields.Many2one("pos.session", string="Sesión")
    name = fields.Char(string="Referencia")
    state = fields.Selection([
        ("draft", "Borrador"),
        ("reserved", "Reservado"),
        ("done", "Confirmado"),
        ("cancel", "Cancelado")
    ], string="Estado", default="draft")
    # note = fields.Text(string="Nota")
    amount_tax = fields.Float(string="Impuestos")
    amount_total = fields.Float(string="Total")
    amount_paid = fields.Float(string="Pagado")
    employee_id = fields.Many2one("hr.employee", string="Empleado")
    cashier = fields.Char(string="Cajero")
    order_id = fields.Many2one("pos.order", string="Orden POS")

    # Relación con líneas
    line_ids = fields.One2many(
        "pos.reserved.line",
        "reserved_id",
        string="Líneas reservadas"
    )
    
class PosReserverdLine(models.Model):
    _name = "pos.reserved.line"
    _description = "Líneas de Apartado POS"

    product_id = fields.Many2one("product.product", string="Producto")
    reserved_id = fields.Many2one("pos.reserved", string="Apartado")
    name = fields.Char(string="Descripción")
    notice = fields.Char(string="Aviso")
    full_product_name = fields.Char(string="Nombre completo del producto")
    customer_note = fields.Text(string="Nota del cliente")
    price_unit = fields.Float(string="Precio Unitario")
    qty = fields.Float(string="Cantidad")
    price_subtotal_incl = fields.Float(string="Subtotal c/IVA")
    discount = fields.Float(string="Descuento (%)")

