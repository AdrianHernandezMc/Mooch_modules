{
    'name': 'Product Moooch',
    'version': '17.0.3.7.1',
    'author': ['Alejandro Rodriguez','Adrian Hernandez'],
    'category': 'Inventory',
    'summary': 'Campos y adecuaciones en productos para Mooch',
    'depends': ['base','product','stock','sale', 'stock_no_negative', 'point_of_sale', 'stock_barcode','account_accountant','l10n_mx','l10n_mx_edi','hr'],
    'license': 'Other proprietary',
    'data': [
        'security/product_mooch_security.xml',
        'security/ir.model.access.csv',
        "reports/product_label_qweb.xml",
        "reports/product_label_qweb_template_from_picking.xml",
        'views/inherit_product_views.xml',
        # 'views/purchase_views.xml',
        'views/stock_picking_label_summary.xml',
        'views/product_barcode_views.xml',
        'views/product_mooch_menu_views.xml',
        'views/res_config_settings_views.xml',
        'data/barcode_parameter_data.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': True,
}