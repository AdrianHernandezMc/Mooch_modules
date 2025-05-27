{
    'name': 'Crédito',

    'technical_name': 'custom_credit_mooch',
    'version': '17.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Gestiona límite y saldo de crédito para clientes en ventas y POS',
    'author': 'Adrian Hernandez',
    'depends': ['sale_management', 'point_of_sale', 'account'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/res_partner_credit_tree.xml',
        'views/menu_credit.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            # 'custom_credit_mooch/static/src/js/create_button.js',
            # 'custom_credit_mooch/static/src/js/popup_alert.js',
            # 'custom_credit_mooch/static/src/xml/pos_product_screen_button.xml',
            # 'custom_credit_mooch/static/src/xml/pos_pop_up.xml',
            # 'custom_credit_mooch/static/src/js/payment_button_patch.js',
            'custom_credit_mooch/static/src/js/popup_credit_terms.js',
            'custom_credit_mooch/static/src/js/payment_credit_button_patch.js',
            'custom_credit_mooch/static/src/xml/pos_payment_button.xml',
            'custom_credit_mooch/static/src/xml/popup_credit_terms.xml',
        ],
    },
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}