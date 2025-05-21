from odoo import models, fields, api, _
import pyodbc
import logging
from contextlib import closing
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class SqlServerImporter(models.Model):
    _name = 'sql.server.importer'
    _description = 'Conector a SQL Server'

    def importar_datos_clientes(self):

        # PRODUCCION #

        # server = '192.168.3.2\SqlserverTlajo'
        # database = 'dbCredito'
        # username = 'aplicaciones'
        # password = 'mooch98_33'

        # PRUEBAS #
        config = self.env['ir.config_parameter'].sudo()
        server = config.get_param('sqlserver.server')
        database = config.get_param('sqlserver.database')
        username = config.get_param('sqlserver.username')
        password = config.get_param('sqlserver.password')

        connection_string = (
            f'DRIVER={{ODBC Driver 17 for SQL Server}};'
            f'SERVER={server};'
            f'DATABASE={database};'
            f'UID={username};'
            f'PWD={password}'
        )

        try:
            with closing(pyodbc.connect(connection_string)) as conn:
                with closing(conn.cursor()) as cursor:
                    query = """
                            SELECT cl.cuenta AS cuenta_cliente, \
                                   cg.ctaAdicional AS cuenta_adicional_mooch, \
                                   cl.nombre AS nombre_cliente, \
                                   cl.paterno AS apellido_paterno, \
                                   cl.materno AS apellido_materno, \
                                   cl.limcred AS limite_credito, \
                                   ISNULL(SUM(cg.Saldoact), 0) AS total_cargos, \
                                   (cl.limcred - ISNULL(SUM(cg.Saldoact), 0)) AS saldo_disponible
                            FROM clientes cl
                                     LEFT JOIN cargos cg ON cl.cuenta = cg.cuenta
                            GROUP BY cl.cuenta, cg.ctaAdicional, cl.nombre, cl.paterno, cl.materno, cl.limcred \
                            """
                    cursor.execute(query)
                    records_to_create = []
                    for row in cursor:
                        existing_record = self.env['res.partner'].search(
                            [('cuenta_cliente_mooch', '=', row.cuenta_cliente)], limit=1)
                        if existing_record:
                            existing_record.write({
                                'cuenta_adicional_mooch': row.cuenta_adicional_mooch,
                                'nombre_mooch': row.nombre_cliente,
                                'paterno_mooch': row.apellido_paterno,
                                'materno_mooch': row.apellido_materno,
                                'limcred_mooch': float(row.limite_credito) if row.limite_credito is not None else 0.0,
                                'saldo_disponible_mooch': float(
                                    row.saldo_disponible) if row.saldo_disponible is not None else 0.0,
                            })
                        else:
                            records_to_create.append({
                                'name': (row.nombre_cliente or '') + ' ' + (row.apellido_paterno or '') + ' ' + (
                                            row.apellido_materno or ''),
                                'cuenta_cliente_mooch': row.cuenta_cliente,
                                'cuenta_adicional_mooch': row.cuenta_adicional_mooch,
                                'nombre_mooch': row.nombre_cliente,
                                'paterno_mooch': row.apellido_paterno,
                                'materno_mooch': row.apellido_materno,
                                'limcred_mooch': float(row.limite_credito) if row.limite_credito is not None else 0.0,
                                'saldo_disponible_mooch': float(
                                    row.saldo_disponible) if row.saldo_disponible is not None else 0.0,
                            })
                    if records_to_create:
                        new_records = self.env['res.partner'].create(records_to_create)
                        self.env.cr.commit()
                        raise ValidationError(
                            f"Se importaron {len(new_records)} registros nuevos y se actualizaron existentes")
                    else:
                        raise ValidationError('Se actualizaron registros existentes')
        except pyodbc.Error as e:
            error_msg = f"Error de conexión a SQL Server: {str(e)}"
            _logger.error(error_msg)
            raise self.env['res.config.settings'].get_config_warning(error_msg)
