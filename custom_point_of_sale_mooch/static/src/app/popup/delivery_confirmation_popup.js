/** @odoo-module **/

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export class DeliveryConfirmationPopup extends Component {
    static template = "custom_point_of_sale_mooch.DeliveryConfirmationPopup";
    
    setup() {
        this.pos = usePos();
    }

    confirmDelivery() {
        this.props.close({ confirmed: true, wantsDelivery: true });
    }

    skipDelivery() {
        this.props.close({ confirmed: true, wantsDelivery: false });
    }

    cancel() {
        this.props.close({ confirmed: false, wantsDelivery: false });
    }
}

registry.category("pos.popups").add("DeliveryConfirmationPopup", DeliveryConfirmationPopup);