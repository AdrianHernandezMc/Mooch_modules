/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { CashMovePopup } from "@point_of_sale/app/navbar/cash_move_popup/cash_move_popup";
import { Navbar } from '@point_of_sale/app/navbar/navbar';
import { _t } from "@web/core/l10n/translation";
import { useState } from '@odoo/owl';


patch(CashMovePopup.prototype, {
    async setup() {
        await super.setup();
        this.pos = this.env.services.pos; 
        this.orm = this.env.services.orm;

        const totales =  Number(await this.pos.sum_cash()) || 0;
        const cash_out =  Number(await this.pos.get_cash_out()) || 0;
        //this.totalCashReceived = totales;
        //this.totalCashReceived = totales- cash_out;
        // const currentUserId = this.pos.user.id; // ID del usuario actual
        const currentEmployer_id = this.pos.get_cashier()?.id
        const advancedEmployeeIds = this.pos.config.advanced_employee_ids; // Lista de IDs
        const isAdvancedUser = advancedEmployeeIds.includes(currentEmployer_id);

        if (isAdvancedUser) {
            console.log("Este usuario" + currentEmployer_id + "tiene derechos avanzados en el POS.");
            this.totalCashReceived = totales- cash_out;
        } else {
            console.log("Este usuario NO xxx tiene derechos avanzados.");
            this.totalCashReceived = 0;
        }
        this.render(true);
    },
        fmt(v) {
        return this.env.utils.formatCurrency(v || 0, { currency: this.pos.currency });
    },
});

patch(Navbar.prototype, {
    setup() {
        super.setup();
        this.state = useState({ showCashMoveOverride: false });
    },

    get showCashMoveButton() {
        const currentEmployer_id = this.pos.get_cashier()?.id
        const advancedEmployeeIds = this.pos.config.advanced_employee_ids; // Lista de IDs
        const isAdvancedUser = advancedEmployeeIds.includes(currentEmployer_id);
        // usa el estado para controlar la visibilidad
        console.log("usuaruio es? ", isAdvancedUser);
        if (isAdvancedUser) {
            return true;
        }
        else {
            return false //this.state.showCashMoveOverride;
        }

    },

    onCashMoveToggle() {
        alert("Estatecash")
        this.state.showCashMoveOverride = !this.state.showCashMoveOverride;
    }
});




