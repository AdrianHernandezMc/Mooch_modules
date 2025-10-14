/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class MaskedInputPopup extends Component {
    setup() {
        this.popup = useService("popup");
        this.state = { value: "" };
        this.title = "Reembolso por Ticket";
        this.lastKey = null;

    }
    
    trackKey(ev) {
        this.lastKey = ev.key;
    }

    formatInput(ev) {
        let raw = ev.target.value.replace(/[^0-9]/g, "").slice(0, 12);
        //let raw = ev.target.value.replace("s","").slice(0, 12);
        console.log("raw",raw)
        let formatted = "" 
        if (raw.length > 0) formatted += raw.slice(0, 5);
        if (raw.length >= 6 && this.lastKey !== "Backspace") {
            formatted += "-" + raw.slice(5, 8);
        } else if (raw.length >= 6) {
            formatted += raw.slice(5, 8); // sin guión
        }
        if (raw.length >= 9 && this.lastKey !== "Backspace") {
            formatted += "-" + raw.slice(8, 12);
        } else if (raw.length >= 9) {
            formatted += raw.slice(8, 12);
        }
        this.state.value = formatted;
        ev.target.value = formatted; // ← fuerza el valor en el input
    }

    async confirm() {
        this.props.resolve({ confirmed: true, payload: this.state.value });
        this.props.close?.();
    }

    cancel() {
        this.props.resolve({ confirmed: false });
        this.props.close?.();
    }
}
MaskedInputPopup.template = "custom_point_of_sale.masked_intput_popup";