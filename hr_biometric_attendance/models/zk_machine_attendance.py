# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Cybrosys Techno Solutions (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
from odoo import api, fields, models


class ZkMachineAttendance(models.Model):
    """Model to hold RAW data from the biometric device"""
    _name = 'zk.machine.attendance'
    _description = 'Biometric Raw Data'
    # ⚠️ ELIMINAR COMPLETAMENTE: _inherit = 'hr.attendance'

    # Campos básicos (SOLO para almacenar datos crudos del biométrico)
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    punching_time = fields.Datetime(string='Punching Time', required=True)
    
    device_id_num = fields.Char(string='Biometric Device ID')
    punch_type = fields.Selection([
        ('0', 'Check In'), ('1', 'Check Out'),
        ('2', 'Break Out'), ('3', 'Break In'),
        ('4', 'Overtime In'), ('5', 'Overtime Out'),
        ('255', 'Duplicate')], string='Punching Type')
    
    attendance_type = fields.Selection([
        ('1', 'Finger'), ('15', 'Face'),
        ('2', 'Type_2'), ('3', 'Password'),
        ('4', 'Card'), ('255', 'Duplicate')], string='Category')
    
    address_id = fields.Many2one('res.partner', string='Working Address')
    
    # ⚠️ ELIMINAR estos campos que vienen de hr.attendance:
    # check_in, check_out, etc.