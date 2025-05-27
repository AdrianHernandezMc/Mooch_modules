/** @odoo-module **/

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useState } from "@odoo/owl";

export class CreditTermsPopup extends AbstractAwaitablePopup {
    static template = "custom_credit_mooch.CreditTermsPopup";
    static defaultProps = {
        months: [1, 3, 6, 12],
        defaultMonth: 3,
    };

    setup() {
        super.setup();
        this.state = useState({ selected: this.props.defaultMonth });
    }

    select(month) {
        this.state.selected = month;
    }

    confirm() {
        this.props.resolve({ confirmed: true, months: this.state.selected });
        this.props.close();
    }

    cancel() {
        this.props.resolve({ confirmed: false });
        this.props.close();
    }
}
