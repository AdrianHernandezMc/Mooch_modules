/** @odoo-module **/

import { Component } from "@odoo/owl";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { CustomAlertPopup } from "@custom_credit_mooch/js/popup_alert";

export class CreateButton extends Component {
    static template = "point_of_sale.CreateButton";

    setup() {
        this.popup = useService("popup");
        this.pos = usePos();
    }

    async onClick() {
        this.popup.add(CustomAlertPopup, {
            title: "Alerta personalizada",
            body: "Este es un popup personalizado",
        });
    }
}

ProductScreen.addControlButton({
    component: CreateButton,
    condition: () => true,
});
