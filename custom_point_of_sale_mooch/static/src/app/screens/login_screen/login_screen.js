/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { LoginScreen } from "@pos_hr/app/login_screen/login_screen";

patch(LoginScreen.prototype, {
    cancelarYSalir() {
        this.props.resolve({ confirmed: false, payload: false });
        this.pos.closeTempScreen();
        this.pos.redirectToBackend();
    },
});