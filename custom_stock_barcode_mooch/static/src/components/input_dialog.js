/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

export class InputDialog extends Component {
    setup() {
        this.state = useState({ value: "" });
        this.title = this.props.title || _t("Información Requerida");
    }

    _confirm() {
        this.props.confirm(this.state.value);
        this.props.close();
    }

    _cancel() {
        this.props.close();
    }
}

InputDialog.template = "custom_stock_barcode_mooch.InputDialog";
InputDialog.components = { Dialog };
InputDialog.props = {
    title: { type: String, optional: true },
    confirm: { type: Function },
    close: { type: Function },
};