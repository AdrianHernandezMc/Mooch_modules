/** @odoo-module */

import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { patch } from "@web/core/utils/patch";
import { onMounted, useRef } from "@odoo/owl";

patch(NumberPopup.prototype, {
    setup() {
        super.setup();
        this.txtInput = useRef("text-input-pw");

        onMounted(() => {
            // Solo enfocamos si es password
            if (this.props.isPassword && this.txtInput.el) {
                this.txtInput.el.focus();
            }
        });
    },

    onTextInput(ev) {
        this.state.buffer = ev.target.value;
    },

    getPayload() {
        if (this.props.isPassword) {
            return this.state.buffer;
        }
        return super.getPayload();
    }
});