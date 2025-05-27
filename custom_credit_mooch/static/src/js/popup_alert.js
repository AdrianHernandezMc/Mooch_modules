/** @odoo-module **/

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

export class CustomAlertPopup extends AbstractAwaitablePopup {
    static template = "custom_credit_mooch.CustomAlertPopup";
    static defaultProps = {
        title: '',
        body: '',
    };
}
