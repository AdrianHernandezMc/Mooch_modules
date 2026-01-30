{
    'name': 'Custom Stock Barcode Mooch',
    'version': '17.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Personalizaciones completas para Odoo Barcode (Mooch)',
    'description': """
        Módulo de personalización para Odoo Enterprise Stock Barcode.
        
        Funcionalidades actuales:
        - Botón de 'Guardar' (Save) sin validar en la pantalla de operaciones.
        - Estructura lista para futuras modificaciones de lógica y vista.
    """,
    'author': 'Mooch',
    'depends': ['stock_barcode', 'web', 'stock'],
    'data': [
            'views/stock_quant_views.xml',
            'views/stock_move_line_views.xml',
        ],
    'assets': {
        'web.assets_backend': [
            'custom_stock_barcode_mooch/static/src/components/main_patch.xml',
            'custom_stock_barcode_mooch/static/src/components/main_patch.js',
            'custom_stock_barcode_mooch/static/src/components/line_patch.xml',
            'custom_stock_barcode_mooch/static/src/components/input_dialog.xml',
            'custom_stock_barcode_mooch/static/src/components/input_dialog.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'OPL-1',
}