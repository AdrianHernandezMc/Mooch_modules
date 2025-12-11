/** @odoo-module */

import { CashMovePopup } from "@point_of_sale/app/navbar/cash_move_popup/cash_move_popup";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";

patch(CashMovePopup.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.savedMoneyDetails = null;
    },

    async openDetailsPopup() {
        try {
            // Abrimos el popup
            const { confirmed, payload } = await this.popup.add(MoneyDetailsPopup, {
                moneyDetails: this.savedMoneyDetails, 
            });

            if (confirmed) {
                // Guardamos el estado para la próxima vez
                this.savedMoneyDetails = payload.moneyDetails;
                
                // 1. Asignar monto total
                if (payload.total !== undefined) {
                    this.state.amount = payload.total.toFixed(2);
                }

                // 2. Generar el Texto del Motivo (En Lista Vertical)
                try {
                    const parts = [];
                    
                    // Clonamos los billetes para ordenarlos
                    let billsCopy = [...(this.pos.bills || [])];

                    // ORDENAMOS: De Mayor a Menor ($1000 -> $0.50)
                    billsCopy.sort((a, b) => b.value - a.value);

                    for (const bill of billsCopy) {
                        // Buscamos usando el VALOR como clave
                        let qty = 0;
                        if (payload.moneyDetails) {
                            qty = payload.moneyDetails[bill.value] || payload.moneyDetails[String(bill.value)];
                        }

                        if (qty > 0) {
                            const valueStr = this.env.utils.formatCurrency(bill.value);
                            // Formato de línea: "3 x $ 500.00"
                            parts.push(`${qty} x ${valueStr}`);
                        }
                    }

                    // AQUI ESTÁ EL CAMBIO PARA LISTA VERTICAL
                    if (parts.length > 0) {
                        // Usamos '\n' que significa "Salto de Línea"
                        this.state.reason = parts.join('\n');
                    }
                } catch (err) {
                    console.error("Error generando texto:", err);
                }
            }
        } catch (e) {
            console.error("Error popup:", e);
        }
    },

    get currentCashBalance() {
        try {
            if (this.pos && this.pos.get_session()) {
                return this.pos.get_session().cash_register_balance_end_real || 0;
            }
            return 0;
        } catch (e) {
            return 0;
        }
    },

    fmt(value) {
        try {
            return this.env.utils.formatCurrency(value);
        } catch (e) {
            return "0.00";
        }
    }
});