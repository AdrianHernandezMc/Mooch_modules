/** @odoo-module **/
import { DiscountButton } from "@pos_discount/overrides/components/discount_button/discount_button";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

patch(DiscountButton.prototype, {
    async click() {
        const order = this.pos.get_order();
        const discountLines = order ? order.get_orderlines().filter(l => l.discount > 0) : [];

        if (discountLines.length) {
            this.popup.add(ErrorPopup, {
                title: "Descuentos",
                body: "Ya exite un desuento en la venta",
            });
            return;
        }
        await super.click(); // 🟢 conserva la lógica original
    },
});
