{
    'name': 'Clientes Mooch',
    'version': '1.1',
    'summary': 'Importar y exportar creditos y clientes mooch',
    'author': 'Development Mooch',
    'category': 'Tools',
    'depends': ['base', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/sql_importer_views.xml',
        'views/res_partner_views.xml',
        'data/ir_config_parameter.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}