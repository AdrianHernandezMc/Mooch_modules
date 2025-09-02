/** @odoo-module */

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class Reserved extends Component {
    static template = "point_of_sale.reserved";
    
    setup() {
        //this.pos = usePos();
        this.orm = useService("orm");
        this.action = useService("action"); // o usa window.open si prefieres nueva pestaña
        this.pos = useService("pos");               // ← aquí obtienes el PosStore
        this.cfgId = null;
    }

    click() {

        //const cfgId = this.pos.config.id;
        //const pid =  this.orm.call("pos.config", "get_changes_product_id", [cfgId], {});
        //console.log("🟢 changes_product_id (RPC) =", pid);

        //window.open('/web#action=custom_point_of_sale_mooch.exchange_change_action', '_blank');
        this.showScreen("custom_point_of_sale_mooch.exchange_change_action", { recordId: null });
    }
}

ProductScreen.addControlButton({
    component: Reserved,
    condition: function () {
        return true;
    },
});