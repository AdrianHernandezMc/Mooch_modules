{
    'name': "custom_point_of_sale_mooch",
    'version': '17.0.1.2.0',
    'category': 'Point of Sale',
    'summary': 'Reembolsos POS via Loyalty',
    'depends': ['base','point_of_sale', 'loyalty','pos_loyalty','web','product'],
    'data':  [
        'security/ir.model.access.csv',
        'views/changes_menu.xml',
        'views/res_config_settings_views.xml',
        'views/pos_payment_method_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            # Archivos JS
            "custom_point_of_sale_mooch/static/src/js/pos_store.js",
            "custom_point_of_sale_mooch/static/src/js/order_selector.js",
            "custom_point_of_sale_mooch/static/src/js/product_screen_coupon.js",
            "custom_point_of_sale_mooch/static/src/js/refund_coupon.js",
            "custom_point_of_sale_mooch/static/src/js/selection_popup.js",

            # Popups
            "custom_point_of_sale_mooch/static/src/app/popup/home_delivery_popup.js",
            "custom_point_of_sale_mooch/static/src/app/popup/productscreen_help.js",
            "custom_point_of_sale_mooch/static/src/app/popup/hide_passwordpopup.js",


            # Screens
            "custom_point_of_sale_mooch/static/src/app/screens/receipt_screen/order_receipt.js",
            "custom_point_of_sale_mooch/static/src/app/screens/reserved/btn_reserved.js",
            "custom_point_of_sale_mooch/static/src/app/screens/paymentscreen/paymentscreen.js",
            "custom_point_of_sale_mooch/static/src/app/screens/productscreen/productscreen.js",
            "custom_point_of_sale_mooch/static/src/app/screens/productscreen/product_list/product_list.js",
            "custom_point_of_sale_mooch/static/src/app/screens/ticketscreen/ticketscreen.js",


            # Models y otros
            "custom_point_of_sale_mooch/static/src/app/store/models.js",
            "custom_point_of_sale_mooch/static/src/app/navbar/navbar.js",

            # Archivos XML
            "custom_point_of_sale_mooch/static/src/xml/refund_coupon.xml",
            "custom_point_of_sale_mooch/static/src/xml/process_exchange.xml",
            "custom_point_of_sale_mooch/static/src/app/screens/reserved/btn_reserved.xml",
            "custom_point_of_sale_mooch/static/src/app/screens/receipt_screen/receipt_screen.xml",
            "custom_point_of_sale_mooch/static/src/app/screens/paymentscreen/paymentscreen.xml",
            "custom_point_of_sale_mooch/static/src/app/popup/productscreen_help.xml",
            "custom_point_of_sale_mooch/static/src/app/popup/hide_passwordpopup.xml",
            "custom_point_of_sale_mooch/static/src/app/screens/productscreen/productscreen.xml",
            "custom_point_of_sale_mooch/static/src/app/screens/productscreen/control_buttons/control_buttons_popup.xml",
            "custom_point_of_sale_mooch/static/src/app/navbar/cash_move_receipt/cash_move_popup.xml",

            # CSS
            "custom_point_of_sale_mooch/static/src/css/refund_coupon.css",
            "custom_point_of_sale_mooch/static/src/app/screens/receipt_screen/order_receipt.css",
            "custom_point_of_sale_mooch/static/src/app/screens/paymentscreen/paymentscreen.css",
            "custom_point_of_sale_mooch/static/src/app/popup/productscreen_help.css",
            "custom_point_of_sale_mooch/static/src/app/screens/productscreen/productscreen.css",
        ],
        "point_of_sale.assets_prod": [
            "custom_point_of_sale_mooch/static/src/app/screens/receipt_screen/receipt_screen.xml",
            "custom_point_of_sale_mooch/static/src/app/screens/receipt_screen/order_receipt.css",
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}