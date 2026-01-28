{
    'name': 'Custom Stock Move',
    'version': '17.0.0.1.0',
    'author': ['Baruc Alvarez','Adrian Hernandez'],
    'category': 'Inventory',
    'summary': 'Campos traslados para Mooch',
    'depends': ['stock','hr','stock_account','product_mooch','purchase_stock'],
    'license': 'Other proprietary',
    'data': [
        "security/ir.model.access.csv",
        'views/stock_picking_views.xml',
        'views/stock_move_views.xml',
        'views/stock_picking_purchase_totals_views.xml',
        'views/stock_move_price_columns_views.xml',
        'views/stock_transfer_product_selector_wizard_views.xml',
        'data/cron_data.xml',
        'data/data_recalculate.xml'
    ],
    'installable': True,
    'application': True,
}