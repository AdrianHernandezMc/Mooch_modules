/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useState } from "@odoo/owl";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup"; // Odoo 17



// 👉 Parchea PaymentScreen para mostrar input de Transaction ID
patch(PaymentScreen.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.txState = useState({ value: "" });
    },

    get selectedPaymentLine() {
        return this.pos.get_order()?.selected_paymentline || null;
    },

    // ✅ Requisito: si el nombre del método contiene 'Tarjeta de crédito' o 'Tarjeta de débito'
    get requiresTxId() {
        const line = this.selectedPaymentLine;
        const method = line?.payment_method;
        console.log("line",line)
        console.log("method.require_transaction_id",method)
        //console.log("method.require_transaction_id",method.require_transaction_id)
        if (!method) return false;
        // insensitive a acentos/mayúsculas
        const name = (method.name || "")
            .normalize("NFD").replace(/\p{Diacritic}/gu, "")
            .toLowerCase();
        return /t.*credito/.test(name) || /t.*debito/.test(name) || !!method.require_transaction_id;
    },

    onTxInput(ev) {

        const val = ev.target.value.trim();
        this.txState.value = val;
        const line = this.selectedPaymentLine;
        if (line) {
            line.transaction_id = val; // <- guardamos en la paymentline
        }
    },

    async validateOrder() {
        // Bloquea validación si hace falta y no se capturó
        const line = this.selectedPaymentLine;
        if (this.requiresTxId && (!line?.transaction_id || !line.transaction_id.trim())) {
            await this.popup.add(ErrorPopup, {
                title: _t("Falta folio de la terminal"),
                body: _t("Captura el Transaction ID para pagos con tarjeta."),
            });
            return;
        }
        return super.validateOrder(...arguments);
    },
});

