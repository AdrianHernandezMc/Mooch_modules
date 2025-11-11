/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { ApartadosPopup } from "@custom_point_of_sale_mooch/app/screens/reserved/reserved";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class Reserved extends Component {
    static template = "point_of_sale.reserved";
    
    setup() {
        this.popup = useService("popup");
        this.pos = useService("pos");
    }

    async click() {
        const order = this.pos.get_order();
        if (!order) return;

        console.log("lines", order.get_orderlines())

        // 🔵 Tomamos las líneas del pedido actual
        const lines = order.get_orderlines().map(l => ({
            product_id: l.product.id,
            name: l.product.display_name,
            qty: l.quantity,
            price_unit: l.get_price_with_tax(),
            price_subtotal_incl: l.get_price_with_tax(),
            discount: l.discount,
            full_product_name: l.product.full_name || l.product.display_name + "- ["+ l.barcode + "]"  ,
        }));


        // 🟢 Abrimos el popup con las líneas
        await this.popup.add(ApartadosPopup, { title: "Apartar productos", lines: lines || [] });
        //this.popup.add(ApartadosPopup);
    }
}

ProductScreen.addControlButton({
    component: Reserved,
    condition: function () {
        return true;
    },
});
