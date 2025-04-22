from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):  # ¡Cambiado a TransientModel!
    _inherit = 'res.config.settings'

    sat_username = fields.Char(
        string='Usuario SAT',
        config_parameter='l10n_mx_sat_sync.sat_username'
    )

    sat_password = fields.Char(
        string='Contraseña SAT',
        config_parameter='l10n_mx_sat_sync.sat_password'
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            sat_username=params.get_param('l10n_mx_sat_sync.sat_username', default=''),
            sat_password=params.get_param('l10n_mx_sat_sync.sat_password', default=''),
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('l10n_mx_sat_sync.sat_username', self.sat_username)
        self.env['ir.config_parameter'].sudo().set_param('l10n_mx_sat_sync.sat_password', self.sat_password)