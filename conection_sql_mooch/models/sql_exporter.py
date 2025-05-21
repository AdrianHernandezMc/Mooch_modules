from odoo import models, fields, api
from odoo.exceptions import ValidationError
import pyodbc
import logging
from contextlib import closing

_logger = logging.getLogger(__name__)

class SqlExporter(models.Model):
    _name = 'sql.exporter'
    _description = 'Envio de información a SQL Server Mooch'

    def exportar_datos_clientes(self, amount, cuenta_cliente_mooch):
        cantidad = amount
        cuenta = cuenta_cliente_mooch

        if not cantidad or not cuenta:
            raise ValidationError("Los datos enviados no son válidos o estan incompletos.")

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
                    query = "Select * from cargos"
                    cursor.execute(query)
                    print(cursor.fetchall())
                    # query = """
                    #     UPDATE cargos
                    #     SET Saldoact = Saldoact - ?
                    #     WHERE cuenta = ?
                    # """
                    # cursor.execute(query, (cantidad, cuenta))
                    # conn.commit()  # Muy importante para que se aplique el UPDATE
                    _logger.info("Actualización exitosa para cuenta eeñejo")

            return {'status': 'ok', 'mensaje': 'Actualización realizada con éxito'}

        except pyodbc.Error as e:
            error_msg = f"Error de conexión o ejecución en SQL Server: {str(e)}"
            _logger.error(error_msg)
            raise ValidationError(error_msg)
