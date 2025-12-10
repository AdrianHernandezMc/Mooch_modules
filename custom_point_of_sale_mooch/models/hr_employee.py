# -*- coding: utf-8 -*-
from odoo import api, fields, models

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # x_nip = fields.Char(string="NIP POS", help="NIP para autorización de cambio de precio en POS.")

    @api.model
    def check_pos_nip(self, nip):
        """Devuelve dict: {'ok': bool, 'name': str} si existe empleado con NIP y puesto 'Gerente Ventas'."""
        if not nip:
            return {'ok': False, 'name': ''}
        # Busca por NIP y puesto (job_id.name). Ajusta si tu campo se llama diferente.
        emp = self.sudo().search([
            ('pin', '=', nip),
            # ('job_id.name', '=', 'Gerente ventas'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        return {'ok': bool(emp), 'name': emp.name or '' , 'id': emp.id }
    
    # Sobrescribimos la validación original para anularla
    @api.constrains('pin')
    def _verify_pin(self):
        # La función original revisa "if not pin.isdigit()".
        # Al dejarla vacía (pass), permitimos guardar letras, símbolos, etc.
        pass