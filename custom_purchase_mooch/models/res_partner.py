from odoo import models, api, _
from odoo.exceptions import ValidationError
import psycopg2

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def init(self):
        # Este init se ejecuta al (re)instalar el módulo
        self.env.cr.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relname = 'uq_partner_supplier_name_partial'
                ) THEN
                    CREATE UNIQUE INDEX uq_partner_supplier_name_partial
                        ON res_partner (lower(name))
                        WHERE supplier_rank > 0;
                END IF;
            END
            $$;
        """)

    @api.model
    def create(self, vals):
        try:
            return super().create(vals)
        except psycopg2.errors.UniqueViolation:
            # El índice parcial disparó un UniqueViolation
            raise ValidationError(
                _('No puedes crear dos proveedores con el mismo nombre.')
            )

    def write(self, vals):
        try:
            return super().write(vals)
        except psycopg2.errors.UniqueViolation:
            raise ValidationError(
                _('No puedes renombrar un proveedor a un nombre que ya existe.')
            )