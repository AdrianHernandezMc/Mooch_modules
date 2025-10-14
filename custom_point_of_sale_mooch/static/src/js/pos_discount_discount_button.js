/** @odoo-module **/
import { DiscountButton } from "@pos_discount/overrides/components/discount_button/discount_button";
import { patch } from "@web/core/utils/patch";
import { useBus } from "@web/core/utils/hooks";

const _superSetup = DiscountButton.prototype.setup;

const _superApplyDiscount = DiscountButton.prototype.apply_discount;


patch(DiscountButton.prototype, {
    setup() {
        _superSetup.apply(this, arguments);
        // Tu lógica adicional¿
        useBus(this.env.bus, "trigger-discount", (event) => {
            const { pc } = event.detail;
            this.apply_discount(pc);
        });
    },

    apply_discount(pc) {
        console.log(pc)
        _superApplyDiscount.call(this, pc); // si quieres conservar la lógica original
        console.log("Extendido desde mi módulo");
    },
});
