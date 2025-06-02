{
    'name': 'Compras Mooch',

    'technical_name': 'custom_purchase_mooch',
    'version': '17.0.1.0.0',
    'category': 'Purcharse',
    'summary': 'Agregado de nuevos campos y cambios al modulo raiz de compras de odoo',
    'author': 'Adrian Hernandez',
    'depends': ['purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_views.xml',
        'views/product_selector_views.xml',
    ],
    'assets': {
    },
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}