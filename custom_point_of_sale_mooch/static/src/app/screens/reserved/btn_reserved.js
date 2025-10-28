/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class Reserved extends Component {
    static template = "point_of_sale.reserved";
    
    setup() {
        this.orm = useService("orm");
        this.action = useService("action"); 
        this.pos = useService("pos"); 
        this.cfgId = null;
    }

    click() {

        //const cfgId = this.pos.config.id;
        //const pid =  this.orm.call("pos.config", "get_changes_product_id", [cfgId], {});
        //console.log("🟢 changes_product_id (RPC) =", pid);

        //window.open('/web#action=custom_point_of_sale_mooch.exchange_change_action', '_blank');
        this.showScreen("custom_point_of_sale_mooch.exchange_change_action", { recordId: null });

        //this.popup.add(ApartadosPopup);
    }
}

ProductScreen.addControlButton({
    component: Reserved,
    condition: function () {
        return true;
    },
});

// ProductScreen.addControlButton({
//     component: (_, { popup }) => ({
//         onClick: () => popup.add(ApartadosPopup),
//     }),
//     condition: () => true,
// });