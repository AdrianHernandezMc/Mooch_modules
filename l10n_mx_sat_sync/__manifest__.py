{
    'name': 'Sincronización de CFDI con el SAT',
    'version': '17.0.1.0.0',
    'summary': 'Descarga facturas (CFDI) del SAT automáticamente',
    'author': 'Baruc Alvarez',
    'depends': ['base','l10n_mx_edi', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings.xml',
        'views/sat_sync_views.xml',
    ],
    'licence': 'Other Propietary',
    'installable': True,
    'application': True,
}