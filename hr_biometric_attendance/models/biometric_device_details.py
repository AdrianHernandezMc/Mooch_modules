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
import base64
import binascii
import datetime
import logging
import threading
from threading import Thread
import time
from datetime import timedelta
import pytz
from odoo import api, fields, models, registry, _
from odoo.exceptions import UserError, ValidationError
live_capture_thread = None
_logger = logging.getLogger(__name__)
try:
    from zk import const, ZK
    from zk.finger import Finger
except ImportError:
    _logger.error("Please Install pyzk library.")


class BiometricDeviceDetails(models.Model):
    """Model for configuring and connect the biometric device with odoo"""
    _name = 'biometric.device.details'
    _description = 'Biometric Device Details'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True, help='Record Name')
    device_ip = fields.Char(string='Device IP', required=True,
                            help='The IP address of the Device')
    port_number = fields.Integer(string='Port Number', required=True,
                                 help="The Port Number of the Device")
    address_id = fields.Many2one('res.partner', string='Working Address',
                                 help='Working address of the partner')
    is_live_capture = fields.Boolean('Live Capturing',
                                     help="if enabled, gets the live capture "
                                          "from the device",
                                     readonly=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda
                                     self: self.env.user.company_id.id,
                                 help='Current Company')
    stopwatch_time = fields.Float('Stopwatch timer',
                                  help='Time from Live capture enabled')
    device_name = fields.Char(String='Device Name', readonly=True,
                              help='Device Name')
    device_firmware = fields.Char(String='Device Firmware Version',
                                  readonly=True, help='Device Firmware')
    device_serial_no = fields.Char(String='Device Serial No', readonly=True,
                                   help='Device serial No')
    device_platform = fields.Char(String='Device Platform', readonly=True,
                                  help='Device platform')
    device_mac = fields.Char(String='Device Mac ID', readonly=True,
                             help='Device Mac')
    live_capture_start_time = fields.Datetime('Live Capture Time',
                                              help='The Time When Live '
                                                   'Capture Enabled')

    def device_connect(self, zk):
        """Function for connecting the device with Odoo"""
        try:
            _logger.info(f"Attempting connection to device {self.device_ip}:{self.port_number}")
            conn = zk.connect()
            if conn:
                _logger.info("Connection successful")
            return conn
        except Exception as e:
            _logger.error(f"Error connecting to device: {e}")
            return False

    def action_test_connection(self):
        _logger.info("Starting connection test to device")
        zk = ZK(self.device_ip, port=self.port_number, timeout=60, password=False, ommit_ping=False)
        try:
            _logger.info("Attempting to connect...")
            conn = zk.connect()
            _logger.info("Connection attempt finished")
            if conn:
                _logger.info("Device connection successful during test")
                zk.test_voice(index=0)  # Si el dispositivo tiene esta función, emitirá un sonido de prueba
                conn.disconnect()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': 'Successfully Connected',
                        'type': 'success',
                        'sticky': False
                    }
                }
            else:
                _logger.warning("Failed to establish connection during test")
                raise ValidationError("Failed to establish connection to the device.")
        except Exception as error:
            _logger.error(f"Connection test error: {error}")
            raise ValidationError(f"Connection test error: {error}")

    def action_clear_attendance(self):
        """Methode to clear record from the zk.machine.attendance model and
        from the device"""
        for info in self:
            try:
                machine_ip = info.device_ip
                zk_port = info.port_number
                try:
                    # Connecting with the device
                    zk = ZK(machine_ip, port=zk_port, timeout=30,
                            password=0, force_udp=False, ommit_ping=False)
                except NameError:
                    raise UserError(_(
                        "Please install it with 'pip3 install pyzk'."))
                conn = self.device_connect(zk)
                if conn:
                    conn.enable_device()
                    clear_data = zk.get_attendance()
                    if clear_data:
                        # Clearing data in the device
                        conn.clear_attendance()
                        # Clearing data from attendance log
                        self._cr.execute(
                            """delete from zk_machine_attendance""")
                        current_time = fields.datetime.now().strftime(
                            '%Y-%m-%d %H:%M:%S')
                        message = (f'Attendances Are cleared from the Device on'
                                   f' {current_time} By {self.env.user.name}')
                        self.message_post(body=message)
                        conn.disconnect()
                    else:
                        raise UserError(
                            _('Unable to clear Attendance log.Are you sure '
                              'attendance log is not empty.'))
                else:
                    raise UserError(
                        _('Unable to connect to Attendance Device. Please use '
                          'Test Connection button to verify.'))
            except Exception as error:
                raise ValidationError(f'{error}')

    def action_download_attendance(self):
        """Descarga registros del dispositivo evitando duplicados y el ValidationError de 'ya registró su entrada'."""
        _logger.info("++++++++++++ Descargando asistencia desde el dispositivo ++++++++++++++")
        zk_attendance = self.env['zk.machine.attendance']
        hr_attendance = self.env['hr.attendance']

        # Parámetros de control
        TOL = timedelta(minutes=2)           
        ADJUST_MAX = timedelta(minutes=10)   
        MAX_OPEN = timedelta(hours=16)       

        def _exists_same_in(emp_id, dt_str):
            """¿Ya existe un IN exactamente en dt_str para el empleado (abierto o cerrado)?"""
            return bool(hr_attendance.search_count([
                ('employee_id', '=', emp_id),
                ('check_in', '=', dt_str),
            ]))

        def _safe_create_in(emp, dt_str):
            """Crea IN con deduplicación y tolerancia a ValidationError."""
            if _exists_same_in(emp.id, dt_str):
                _logger.info("[BIO] IN ya existente (misma marca), omitido: %s @ %s", emp.name, dt_str)
                return
            try:
                hr_attendance.create({'employee_id': emp.id, 'check_in': dt_str})
                _logger.info("[BIO] IN creado: %s @ %s", emp.name, dt_str)
            except ValidationError as ve:
                # Evita romper todo el batch: loguea y continúa
                _logger.warning("[BIO] Odoo bloqueó IN para %s @ %s (prob. IN abierto). Omitido. Detalle: %s",
                                emp.name, dt_str, ve)

        def _safe_create_span(emp, in_dt_str, out_dt_str):
            """Crea tramo IN/OUT corto con tolerancia a ValidationError."""
            # Si ya existe ese mismo tramo, no lo dupliques
            existing = hr_attendance.search([
                ('employee_id', '=', emp.id),
                ('check_in', '=', in_dt_str),
                ('check_out', '=', out_dt_str),
            ], limit=1)
            if existing:
                _logger.info("[BIO] Tramo ya existente para %s [%s -> %s], omitido.", emp.name, in_dt_str, out_dt_str)
                return
            try:
                hr_attendance.create({
                    'employee_id': emp.id,
                    'check_in': in_dt_str,
                    'check_out': out_dt_str,
                })
                _logger.info("[BIO] Tramo creado: %s [%s -> %s]", emp.name, in_dt_str, out_dt_str)
            except ValidationError as ve:
                _logger.warning("[BIO] Odoo bloqueó tramo para %s [%s -> %s]. Omitido. Detalle: %s",
                                emp.name, in_dt_str, out_dt_str, ve)

        for info in self:
            machine_ip = info.device_ip
            zk_port = info.port_number

            try:
                zk = ZK(machine_ip, port=zk_port, timeout=15, password=0, force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(_("Pyzk module not Found. Please install it with 'pip3 install pyzk'."))

            conn = self.device_connect(zk)
            if not conn:
                raise UserError(_('Unable to connect to Attendance Device. Please use Test Connection to verify.'))

            # (Opcional) Alinear TZ del dispositivo
            try:
                self.action_set_timezone()
            except Exception:
                pass

            try:
                conn.disable_device()
                attendance_logs = conn.get_attendance() or []

                # Orden cronológico (por si el dispositivo entrega desordenado)
                try:
                    attendance_logs = sorted(attendance_logs, key=lambda a: a.timestamp)
                except Exception:
                    pass

                # TZ del usuario (o UTC)
                tzname = (self.env.user.tz or getattr(self.env.user.partner_id, 'tz', None) or 'UTC')
                local_tz = pytz.timezone(tzname)

                for each in attendance_logs:
                    device_user_id = str(each.user_id) if each.user_id is not None else False
                    if not device_user_id:
                        continue

                    # Empleado por device_id_num + compañía
                    emp = self.env['hr.employee'].with_context(active_test=False).search([
                        ('device_id_num', '=', device_user_id),
                        ('company_id', '=', info.company_id.id),
                        ('device_id', '=', info.id),  # 🔒 asegura que solo traiga del dispositivo correcto
                    ], limit=1)
                    if not emp:
                        _logger.warning("[BIO] Empleado no encontrado para device_id_num=%s en %s (dispositivo %s). Log omitido.",
                                        device_user_id, info.company_id.display_name, info.name)
                        continue
                    if not emp.device_id or emp.device_id.id != self.id:
                        emp.write({'device_id': self.id})

                    # Normaliza hora -> UTC
                    local_dt = local_tz.localize(each.timestamp, is_dst=None)
                    utc_dt = local_dt.astimezone(pytz.utc)
                    atten_time = fields.Datetime.to_string(utc_dt)
                    atten_time_dt = fields.Datetime.from_string(atten_time)
                    atten_date = utc_dt.date()  # 🔥 NUEVO: Obtener fecha del registro

                    # Espejo (evitar duplicado)
                    if not zk_attendance.search([
                        ('employee_id', '=', emp.id),
                        ('device_id_num', '=', device_user_id),
                        ('punching_time', '=', atten_time),
                        ('punch_type', '=', str(each.punch)),
                    ], limit=1):
                        zk_attendance.create({
                            'employee_id': emp.id,
                            'device_id_num': device_user_id,
                            'attendance_type': str(each.status),
                            'punch_type': str(each.punch),
                            'punching_time': atten_time,
                            'address_id': info.address_id.id if info.address_id else False,
                        })

                    punch = int(each.punch) if each.punch is not None else -1

                    # ============== CHECK-IN ==============
                    if punch == 0:
                        # Trae TODOS los abiertos (si los hay), más antiguos primero
                        open_atts = hr_attendance.search([
                            ('employee_id', '=', emp.id),
                            ('check_out', '=', False),
                        ], order='check_in asc')

                        merged_or_skipped = False
                        for open_att in open_atts:
                            # Duplicado exacto (rebote)
                            if open_att.check_in and abs(atten_time_dt - open_att.check_in) <= TOL:
                                _logger.info("[BIO] Duplicado IN omitido: %s @ %s", emp.name, atten_time)
                                merged_or_skipped = True
                                break

                            # IN más temprano que el abierto
                            if open_att.check_in and atten_time_dt < open_att.check_in:
                                delta = open_att.check_in - atten_time_dt
                                if delta <= ADJUST_MAX:
                                    # Ajuste leve (mismo turno)
                                    _logger.info("[BIO] Ajuste IN (más temprano) %s: %s -> %s",
                                                emp.name, open_att.check_in, atten_time)
                                    try:
                                        open_att.write({'check_in': atten_time})
                                    except ValidationError as ve:
                                        _logger.warning("[BIO] Bloqueo ajustando IN para %s @ %s. Omitido. %s",
                                                        emp.name, atten_time, ve)
                                    merged_or_skipped = True
                                    break
                                else:
                                    # 🔥 MODIFICADO: Solo cerrar si NO es del día actual
                                    open_att_date = open_att.check_in.date() if open_att.check_in else None
                                    if open_att_date and open_att_date < current_date:
                                        # Diferencia grande y es día anterior: cerrar abierto
                                        close_at = max(open_att.check_in, atten_time_dt - timedelta(seconds=1))
                                        close_at = min(close_at, open_att.check_in + MAX_OPEN)
                                        _logger.info("[BIO] Cerrando IN OBSOLETO (día anterior) %s: IN %s, OUT %s",
                                                    emp.name, open_att.check_in, close_at)
                                        try:
                                            open_att.write({'check_out': fields.Datetime.to_string(close_at)})
                                        except ValidationError as ve:
                                            _logger.warning("[BIO] Bloqueo cerrando obsoleto de %s. Omitido. %s",
                                                            emp.name, ve)
                                    else:
                                        _logger.info("[BIO] IN anterior del MISMO DÍA mantenido abierto: %s @ %s", 
                                                    emp.name, open_att.check_in)
                                    continue

                            # IN posterior al abierto
                            if open_att.check_in and atten_time_dt >= open_att.check_in:
                                if (atten_time_dt - open_att.check_in) <= MAX_OPEN:
                                    # Mismo turno: segundo IN -> omitir (evita ValidationError)
                                    _logger.info("[BIO] Segundo IN en misma jornada para %s, omitido.", emp.name)
                                    merged_or_skipped = True
                                    break
                                else:
                                    # 🔥 MODIFICADO: Solo cerrar si NO es del día actual
                                    open_att_date = open_att.check_in.date() if open_att.check_in else None
                                    if open_att_date and open_att_date < current_date:
                                        # Abierto muy viejo de día anterior: ciérralo
                                        close_at = min(open_att.check_in + MAX_OPEN, atten_time_dt - timedelta(seconds=1))
                                        _logger.info("[BIO] Cerrando IN MUY ANTIGUO (día anterior) %s: IN %s, OUT %s",
                                                    emp.name, open_att.check_in, close_at)
                                        try:
                                            open_att.write({'check_out': fields.Datetime.to_string(close_at)})
                                        except ValidationError as ve:
                                            _logger.warning("[BIO] Bloqueo cerrando antiguo de %s. Omitido. %s",
                                                            emp.name, ve)
                                    else:
                                        _logger.info("[BIO] IN del MISMO DÍA mantenido abierto: %s @ %s", 
                                                    emp.name, open_att.check_in)
                                    continue

                        if merged_or_skipped:
                            continue

                        # 🔥 MODIFICADO: Verificar abiertos pero permitir del día actual
                        open_today = hr_attendance.search_count([
                            ('employee_id', '=', emp.id), 
                            ('check_out', '=', False),
                            ('check_in', '>=', fields.Datetime.to_string(current_date))  # Solo del día actual
                        ])
                        
                        if open_today:
                            _logger.warning("[BIO] Ya existe IN ABIERTO HOY para %s; nuevo IN @ %s omitido.",
                                            emp.name, atten_time)
                            continue

                        # Extra: dedupe por igualdad exacta de check_in
                        if _exists_same_in(emp.id, atten_time):
                            _logger.info("[BIO] IN duplicado exacto detectado para %s @ %s. Omitido.",
                                        emp.name, atten_time)
                            continue

                        # Crear IN blindado
                        _safe_create_in(emp, atten_time)

                    # ============== CHECK-OUT ==============
                    elif punch == 1:
                        # Abierto cuya hora de entrada sea <= OUT (el más lógico a cerrar)
                        open_att = hr_attendance.search([
                            ('employee_id', '=', emp.id),
                            ('check_out', '=', False),
                            ('check_in', '<=', atten_time),
                        ], order='check_in desc', limit=1)

                        if open_att and open_att.check_in:
                            if atten_time_dt <= open_att.check_in:
                                _logger.warning("[BIO] OUT %s <= IN %s para %s, omitido.",
                                                atten_time, open_att.check_in, emp.name)
                                continue
                            try:
                                open_att.write({'check_out': atten_time})
                                _logger.info("[BIO] OUT aplicado: %s @ %s", emp.name, atten_time)
                            except ValidationError as ve:
                                _logger.warning("[BIO] Bloqueo aplicando OUT para %s @ %s. Omitido. %s",
                                                emp.name, atten_time, ve)
                        else:
                            # No hay IN abierto adecuado -> crear IN sintético 30s antes
                            synthetic_in_dt = atten_time_dt - timedelta(seconds=30)
                            synthetic_in = fields.Datetime.to_string(synthetic_in_dt)
                            _safe_create_span(emp, synthetic_in, atten_time)

                    else:
                        _logger.debug("[BIO] Punch desconocido (%s) para %s @ %s", each.punch, emp.name, atten_time)

                if not self.is_live_capture:
                    current_time = fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    message = _('Datos descargados del dispositivo el %s por %s') % (current_time, self.env.user.name)
                    self.message_post(body=message)

                conn.enable_device()
                conn.disconnect()
                _logger.info("++++++++++++ Descarga finalizada correctamente ++++++++++++++")
                return True

            except Exception as e:
                _logger.exception("Error durante la descarga de asistencia")
                try:
                    conn.enable_device()
                    conn.disconnect()
                except Exception:
                    pass
                raise ValidationError(str(e))

    def action_restart_device(self):
        """For restarting the device"""
        zk = ZK(self.device_ip, port=self.port_number, timeout=15,
                password=0,
                force_udp=False, ommit_ping=False)
        if self.device_connect(zk):
            if self.is_live_capture:
                self.action_stop_live_capture()
            self.device_connect(zk).restart()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Successfully Device Restarted',
                    'type': 'success',
                    'sticky': False
                }
            }
        else:
            raise UserError(_(
                "Please Check the Connection"))

    def schedule_attendance(self):
        """Schedule action for attendance downloading"""
        for record in self.search([]):
            if record.is_live_capture:
                record.action_stop_live_capture()
                record.action_download_attendance()
                record.action_live_capture()
            else:
                record.action_download_attendance()

    def action_live_capture(self):
        """ Enable Live capture With Thread"""
        for info in self:
            machine_ip = info.device_ip
            zk_port = info.port_number
            try:
                self.is_live_capture = True
                self.action_set_timezone()
                instance = ZKBioAttendance(machine_ip, zk_port, info)
                global live_capture_thread
                live_capture_thread = instance
                live_capture_thread.start()
                self.live_capture_start_time = fields.datetime.now()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            except NameError:
                raise UserError(_(
                    "Please install it with 'pip3 install pyzk'."))

    def action_stop_live_capture(self):
        """Function to stop Live capture"""
        try:
            self.is_live_capture = False
            if live_capture_thread:
                live_capture_thread.stop()
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        except NameError:
            raise UserError(_(
                "Please install it with 'pip3 install pyzk'."))

    def action_set_timezone(self):
        """Function to set user's timezone to device"""
        for info in self:
            machine_ip = info.device_ip
            zk_port = info.port_number
            try:
                # Connecting with the device with the ip and port provided
                zk = ZK(machine_ip, port=zk_port, timeout=15,
                        password=0,
                        force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(
                    _("Pyzk module not Found. Please install it"
                      "with 'pip3 install pyzk'."))
            conn = self.device_connect(zk)
            if conn:
                user_tz = self.env.context.get(
                    'tz') or self.env.user.tz or 'UTC'
                user_timezone_time = pytz.utc.localize(fields.Datetime.now())
                user_timezone_time = user_timezone_time.astimezone(
                    pytz.timezone(user_tz))
                conn.set_time(user_timezone_time)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': 'Successfully Set the Time',
                        'type': 'success',
                        'sticky': False
                    }
                }
            else:
                raise UserError(_(
                    "Please Check the Connection"))

    def get_all_users(self):
        """Sincroniza usuarios del biométrico sin duplicar empleados."""
        for info in self:
            machine_ip = info.device_ip
            zk_port = info.port_number
            try:
                zk = ZK(machine_ip, port=zk_port, timeout=15,
                        password=0, force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(_("Pyzk module not Found. Please install it with 'pip3 install pyzk'."))

            conn = self.device_connect(zk)
            if not conn:
                raise UserError(_("Please Check the Connection"))

            users = conn.get_users()
            Employee = self.env['hr.employee'].with_context(active_test=False)

            for user in users:
                device_user_id = str(user.user_id) if user.user_id is not None else False
                if not device_user_id:
                    continue

                domain = [('device_id_num', '=', device_user_id)]
                if info.company_id:
                    domain.append(('company_id', '=', info.company_id.id))

                emp = Employee.search(domain, limit=1)
                vals = {'name': user.name or ''}
                # Asegura que el employee quede ligado al dispositivo actual
                if not emp:
                    create_vals = {
                        'name': user.name or f'Empleado {device_user_id}',
                        'device_id_num': device_user_id,
                        'device_id': info.id,
                        'company_id': info.company_id.id,
                    }
                    # (Opcional) asigna dirección de trabajo si aplica
                    if info.address_id:
                        create_vals['address_id'] = info.address_id.id
                    Employee.create(create_vals)
                else:
                    if emp.device_id.id != info.id:
                        vals['device_id'] = info.id
                    emp.write(vals)

    def set_user(self, employee_id):
        """Function to create or update users"""
        for info in self:
            machine_ip = info.device_ip
            zk_port = info.port_number
            employee = self.env['hr.employee'].browse(int(employee_id))
            try:
                # Connecting with the device with the ip and port provided
                zk = ZK(machine_ip, port=zk_port, timeout=15,
                        password=0,
                        force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(
                    _("Pyzk module not Found. Please install it"
                      "with 'pip3 install pyzk'."))
            conn = self.device_connect(zk)
            if conn:
                last_user = conn.get_users()[-1]
                privilege = 0
                password = ''
                group_id = ''
                card = 0
                conn.enable_device()
                conn.disable_device()
                try:
                    uids = [user.uid for user in conn.get_users()]
                    candidate_uid = last_user.uid + 1
                    while candidate_uid in uids:
                        candidate_uid += 1
                    conn.set_user(candidate_uid, employee.name, privilege,
                                  password, group_id, str(candidate_uid), card)
                except Exception as e:
                    _logger.info(e)
                    raise ValidationError(
                        _(" Here is the user information:\n"
                          "uid: %s\n"
                          "name: %s\n"
                          "privilege: %s\n"
                          "password: %s\n"
                          "group_id: %s\n"
                          "user_id: %s\n"
                          "Here is the debugging information:\n%s\n"
                          "Try Restarting the device")
                        % (candidate_uid, employee.name, privilege, password,
                           group_id, str(candidate_uid), e))
                conn.enable_device()
                if conn.get_users()[-1].name in employee.name:
                    employee.write({
                        'device_id': self.id,
                        'device_id_num': conn.get_users()[-1].user_id
                    })
                    current_time = fields.datetime.now().strftime(
                        '%Y-%m-%d %H:%M:%S')
                    message = (f'New User {employee.name} Created on '
                               f'{current_time} by {self.env.user.name}')
                    self.message_post(body=message)
            else:
                raise UserError(_(
                    "Please Check the Connection"))

    def delete_user(self, employee_id, employee_user_selection):
        """Function to Delete a user"""
        for info in self:
            machine_ip = info.device_ip
            zk_port = info.port_number
            try:
                # Connecting with the device with the ip and port provided
                zk = ZK(machine_ip, port=zk_port, timeout=15,
                        password=0,
                        force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(
                    _("Pyzk module not Found. Please install it"
                      "with 'pip3 install pyzk'."))
            conn = self.device_connect(zk)
            if conn:
                employee = self.env['hr.employee'].browse(int(employee_id))
                employee_name = employee.name
                conn.delete_user(uid=None, user_id=employee.device_id_num)
                employee.write({
                    'device_id_num': False,
                    'device_id': False
                })
                employee.fingerprint_ids.unlink()
                if employee_user_selection == 'both_device':
                    employee.unlink()
                current_time = fields.datetime.now().strftime(
                    '%Y-%m-%d %H:%M:%S')
                message = (f'Deleted User {employee_name} on '
                           f'{current_time} by {self.env.user.name}')
                self.message_post(body=message)
            else:
                raise UserError(_(
                    "Please Check the Connection"))

    def update_user(self, employee_id):
        """Function to Update a user"""
        for info in self:
            machine_ip = info.device_ip
            zk_port = info.port_number
            try:
                # Connecting with the device with the ip and port provided
                zk = ZK(machine_ip, port=zk_port, timeout=15,
                        password=0,
                        force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(
                    _("Pyzk module not Found. Please install it"
                      "with 'pip3 install pyzk'."))
            conn = self.device_connect(zk)
            if conn:
                conn.enable_device()
                conn.disable_device()
                employee = self.env['hr.employee'].browse(int(employee_id))
                for line in conn.get_users():
                    if line.user_id == employee.device_id_num:
                        privilege = 0
                        password = ''
                        group_id = ''
                        user_id = employee.device_id_num
                        card = 0
                        conn.set_user(line.uid, employee.name, privilege,
                                      password, group_id, user_id, card)
                        conn.enable_device()
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'message': 'Successfully Updated User',
                                'type': 'success',
                                'sticky': False
                            }
                        }
                else:
                    raise UserError(_(
                        "Please Check the Connection"))

    def get_device_information(self):
        """Gets device Information"""
        for info in self:
            machine_ip = info.device_ip
            zk_port = info.port_number
            try:
                # Connecting with the device with the ip and port provided
                zk = ZK(machine_ip, port=zk_port, timeout=15,
                        password=0,
                        force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(
                    _("Pyzk module not Found. Please install it"
                      "with 'pip3 install pyzk'."))
            conn = self.device_connect(zk)
            if conn:
                self.device_name = conn.get_device_name()
                self.device_firmware = conn.get_firmware_version()
                self.device_serial_no = conn.get_serialnumber()
                self.device_platform = conn.get_platform()
                self.device_mac = conn.get_mac()
            else:
                raise UserError(_(
                    "Please Check the Connection"))


class ZKBioAttendance(Thread):
    """
    Represents a thread for capturing live attendance data from a ZKTeco
    biometric device.

    Attributes: - machine_ip: The IP address of the ZKTeco biometric device.
    - port_no: The port number for communication with the ZKTeco biometric
    device. - conn: The connection object to the ZKTeco biometric device.

    Methods: - run(): Overrides the run method of the Thread class to capture
    live attendance data.
    """

    def __init__(self, machine_ip, port_no, record):
        """Function to Initialize the thread"""
        Thread.__init__(self)
        self.machine_ip = machine_ip
        self.port_no = port_no
        self.record = record
        self.env = record.env
        self.stop_event = threading.Event()

        zk_device = ZK(
            machine_ip,
            port=port_no,
            timeout=5,
            password=0,
            force_udp=False,
            ommit_ping=False,
        )
        conn = zk_device.connect()
        if conn:
            self.conn = conn
        else:
            raise UserError(_(
                "Please Check the Connection"))

    def run(self):
        """Function to run the Thread"""
        while not self.stop_event.is_set():
            try:
                if not self.conn.end_live_capture:
                    for attendance in self.conn.live_capture(2000):
                        self._data_live_capture()
                time.sleep(10)
            except Exception as e:
                self.env.cr.rollback()  # Rollback the current transaction
                time.sleep(1)

    def stop(self):
        """Stops the live capture and stops the thread"""
        if self.conn:
            self.conn.end_live_capture = True
        self.stop_event.set()

    def _data_live_capture(self):
        """Updated the Live Capture real time"""
        with registry(self.env.cr.dbname).cursor() as new_cr:
            new_env = api.Environment(new_cr, self.env.uid, self.env.context)
            if self.conn.get_attendance():
                self.record.with_env(new_env).action_download_attendance()
            new_cr.commit()