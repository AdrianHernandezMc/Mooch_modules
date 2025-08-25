/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Order } from "@point_of_sale/app/store/models";

patch(Order.prototype, "safe-global-discount-lines", {
    _getGlobalDiscountLines() {
        // Algunas builds usan get_orderlines(), otras this.orderlines
        const lines =
            (this.get_orderlines && this.get_orderlines()) ||
            this.orderlines ||
            [];
        return lines.filter(
            (l) => l && l.reward && l.reward.is_global_discount === true
        );
    },
});

