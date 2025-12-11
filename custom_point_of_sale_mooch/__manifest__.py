{
    'name': "custom_point_of_sale_mooch",
    'version': '17.0.1.2.0',
    'category': 'Point of Sale',
    'summary': 'Reembolsos POS via Loyalty',
    'depends': ['base','point_of_sale','loyalty','pos_loyalty','web','product','pos_discount','pos_hr','stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/changes_menu.xml',
        'views/res_config_settings_views.xml',
        'views/pos_payment_method_views.xml',
        'views/stock_picking_views.xml',
        'views/pos_order_views.xml',
        'views/product_views.xml',

        # Documentos
        'views/report_saledetails_inherit.xml'
    ],
    'assets': {
      'point_of_sale._assets_pos': [
          # JS
          "custom_point_of_sale_mooch/static/src/js/pos_store.js",
          "custom_point_of_sale_mooch/static/src/js/order_selector.js",
          "custom_point_of_sale_mooch/static/src/js/product_screen_coupon.js",
          "custom_point_of_sale_mooch/static/src/js/refund_coupon.js",
          "custom_point_of_sale_mooch/static/src/js/selection_popup.js",
          "custom_point_of_sale_mooch/static/src/js/pos_discount_discount_button.js",
          "custom_point_of_sale_mooch/static/src/js/close_pos_popup.js",
          "custom_point_of_sale_mooch/static/src/overrides/components/discount_button/discount_button.js",

          # Popups
          "custom_point_of_sale_mooch/static/src/app/popup/selection_popup_patch.js",
          "custom_point_of_sale_mooch/static/src/app/popup/delivery_confirmation_popup.js",
          "custom_point_of_sale_mooch/static/src/app/popup/home_delivery_popup.js",
          "custom_point_of_sale_mooch/static/src/app/popup/productscreen_help.js",
          "custom_point_of_sale_mooch/static/src/app/popup/hide_passwordpopup.js",
          "custom_point_of_sale_mooch/static/src/app/popup/masked_input_popup.js",
          "custom_point_of_sale_mooch/static/src/app/popup/number_popup.js",
          "custom_point_of_sale_mooch/static/src/app/utilis/Input_popups/text_inpup_popup.xml",

          # Screens
          "custom_point_of_sale_mooch/static/src/app/screens/login_screen/login_screen.js",
          "custom_point_of_sale_mooch/static/src/app/screens/receipt_screen/order_receipt.js",
          "custom_point_of_sale_mooch/static/src/app/screens/reserved/btn_reserved.js",
          "custom_point_of_sale_mooch/static/src/app/screens/paymentscreen/paymentscreen.js",
          "custom_point_of_sale_mooch/static/src/app/screens/productscreen/productscreen.js",
          "custom_point_of_sale_mooch/static/src/app/screens/productscreen/product_list/product_list.js",
          "custom_point_of_sale_mooch/static/src/app/screens/ticketscreen/ticketscreen.js",
          "custom_point_of_sale_mooch/static/src/app/screens/reserved/reserved.js",

          # Models y navbar
          "custom_point_of_sale_mooch/static/src/app/store/models.js",
          "custom_point_of_sale_mooch/static/src/app/navbar/navbar.js",
          "custom_point_of_sale_mooch/static/src/app/navbar/cash_move_receipt/cash_move_popup.js",

          # XML
          "custom_point_of_sale_mooch/static/src/app/screens/login_screen/login_screen.xml",
          "custom_point_of_sale_mooch/static/src/app/popup/selection_popup_patch.xml",
          "custom_point_of_sale_mooch/static/src/xml/refund_coupon.xml",
          #"custom_point_of_sale_mooch/static/src/xml/process_exchange.xml",
          "custom_point_of_sale_mooch/static/src/app/screens/reserved/btn_reserved.xml",
          "custom_point_of_sale_mooch/static/src/app/screens/receipt_screen/receipt_screen.xml",
          "custom_point_of_sale_mooch/static/src/app/screens/paymentscreen/paymentscreen.xml",
          "custom_point_of_sale_mooch/static/src/app/popup/productscreen_help.xml",
          "custom_point_of_sale_mooch/static/src/app/popup/hide_passwordpopup.xml",
          "custom_point_of_sale_mooch/static/src/app/popup/masked_input_popup.xml",
          "custom_point_of_sale_mooch/static/src/app/popup/number_popup.xml",
          "custom_point_of_sale_mooch/static/src/app/screens/productscreen/productscreen.xml",
          "custom_point_of_sale_mooch/static/src/app/screens/ticketscreen/ticketscreen.xml",
          "custom_point_of_sale_mooch/static/src/app/screens/productscreen/control_buttons/control_buttons_popup.xml",
          "custom_point_of_sale_mooch/static/src/app/screens/productscreen/control_buttons/refund_button/refund_button.xml",
          "custom_point_of_sale_mooch/static/src/app/navbar/cash_move_receipt/cash_move_popup.xml",
          "custom_point_of_sale_mooch/static/src/app/navbar/sale_details_button/sale_details_button.js",
          "custom_point_of_sale_mooch/static/src/app/navbar/sale_details_button/sales_detail_report.xml",
          "custom_point_of_sale_mooch/static/src/app/screens/productscreen/action_pad/action_pad.xml",
          "custom_point_of_sale_mooch/static/src/overrides/components/discount_button/discount_button.xml",
          "custom_point_of_sale_mooch/static/src/app/screens/reserved/reserved.xml",

          # CSS
          "custom_point_of_sale_mooch/static/src/css/refund_coupon.css",
          "custom_point_of_sale_mooch/static/src/app/screens/receipt_screen/order_receipt.css",
          "custom_point_of_sale_mooch/static/src/app/screens/paymentscreen/paymentscreen.css",
          "custom_point_of_sale_mooch/static/src/app/popup/productscreen_help.css",
          "custom_point_of_sale_mooch/static/src/app/popup/masked_input_popup.css",
          "custom_point_of_sale_mooch/static/src/app/screens/productscreen/productscreen.css",
          "custom_point_of_sale_mooch/static/src/app/navbar/cash_move_receipt/cash_move_popup.css",
          "custom_point_of_sale_mooch/static/src/app/screens/reserved/reserved.css",
        
          # Comentados (referencia; no se cargan)
          #'custom_point_of_sale_mooch/static/src/app/screens/productscreen/action_pad/action_pad.xml',
          #'custom_point_of_sale_mooch/static/src/app/screens/PaymentScreen/paymentline_model.js',
          #'custom_point_of_sale_mooch/static/src/js/fixes/safe_global_discount.js',

          # Overrides
          "pos_discount/static/src/overrides/components/discount_button/discount_button.js",
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
