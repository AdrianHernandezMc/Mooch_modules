/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useState } from "@odoo/owl";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup"; // Odoo 17
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.pos.txState = useState({ value: "" });
    },
    async onMounted() {
        //this._super();
        // TicketScreen_onDoRefund bandera que proviene de point_of_sale_mooch.TicketScreen_onDoRefund    
        if (this.pos.TicketScreen_onDoRefund){
            const line = this.selectedPaymentLine;
            line.transaction_id = String(this.pos.sharedtcode);
            this.render();
            this.autoValidate?.();
        }
        else {
            const { confirmed } = this.popup.add(ConfirmPopup, {
            title: _t("Facturacion al cliente"),
            body: _t(
                "Recordar al cliente que la facturación se realiza el mismo día."
            ),
        });
        }
        this.pos.TicketScreen_onDoRefund= false;
        
    },

    async autoValidate() {
        return await this.validateOrder();
    },

    get selectedPaymentLine() {
        return this.pos.get_order()?.selected_paymentline || null;
    },

    //  Requisito: si el nombre del método contiene 'Tarjeta de crédito' o 'Tarjeta de débito'
    get requiresTxId() {
        const line = this.selectedPaymentLine;
        const method = line?.payment_method;

        if (!method) return false;
    
        return !!method.require_transaction_id;
    },
    
    onTxInput(ev) {
        const val = ev.target.value.trim();
        this.pos.txState.value = val;
        const line = this.selectedPaymentLine;
        if (line) {
            line.transaction_id = val; 
        }
    },

    async validateOrder() {
        // Bloquea validación si hace falta y no se capturó
        const line = this.selectedPaymentLine;
        if (this.requiresTxId && (!line?.transaction_id || !line.transaction_id.trim())) {
            await this.popup.add(ErrorPopup, {
                title: _t("Falto caputrar id de la tajeta"),
                body: _t("Captura el Transaction ID para pagos con tarjeta."),
            });
            return;
        }
        return super.validateOrder(...arguments);
    },
});

