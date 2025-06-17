{
    'name': 'POS Alert Message',
    'version': '17.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Muestra un alert al entrar en la pantalla de pago',
    'depends': ['point_of_sale'],
    'assets': {
        'point_of_sale._assets_pos': [
            'custom_pos_alert/static/src/xml/pos_alert_templates.xml',
            'custom_pos_alert/static/src/js/pos_alert.js',
        ],
},
    'installable': True,
    'application': False,
}

