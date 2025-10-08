/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { CashMovePopup } from "@point_of_sale/app/navbar/cash_move_popup/cash_move_popup"; 
import { _t } from "@web/core/l10n/translation";

patch(CashMovePopup.prototype, {
    async setup() {
        await super.setup();
        // this.pos = this.env.pos;
        this.pos = this.env.services.pos; // OWL v1 compatible
        this.orm = this.env.services.orm;

        const totales =  Number(await this.pos.sum_cash()) || 0;
        const cash_out =  Number(await this.pos.get_cash_out()) || 0;
        //this.totalCashReceived = totales;
        console.log("cash_out",cash_out)
        //this.totalCashReceived = totales- cash_out;
        console.log("totalCashReceived",this.totalCashReceived)

        // const currentUserId = this.pos.user.id; // ID del usuario actual
        const currentEmployer_id = this.pos.get_cashier()?.id

        // console.log("username",this.pos.user.name)
        // console.log("currentUserId",currentUserId)
        // let currentEmployer_id = await this.orm.call(
        //     'hr.employee',
        //     'search_read',
        // [[['id', '=', currentUserId]]],
        // { fields: ['id'], limit: 1 }
        //  );

        console.log("currentEmployer_id",currentEmployer_id)
        
        // currentEmployer_id =  currentEmployer_id.length ? currentEmployer_id[0].id : null;

        const advancedEmployeeIds = this.pos.config.advanced_employee_ids; // Lista de IDs
        console.log("advancedEmployeeIds",advancedEmployeeIds)
        
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





