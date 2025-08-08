{
    'name': 'Custom Stock Move',
    'version': '17.0.0.1.0',
    'author': ['Baruc Alvarez'],
    'category': 'Inventory',
    'summary': 'Campos traslados para Mooch',
    'depends': ['stock','hr','stock_account','product_mooch'],
    'license': 'Other proprietary',
    'data': [
        'views/stock_picking_views.xml',
        'views/stock_move_views.xml',
    ],
    'installable': True,
    'application': True,
}