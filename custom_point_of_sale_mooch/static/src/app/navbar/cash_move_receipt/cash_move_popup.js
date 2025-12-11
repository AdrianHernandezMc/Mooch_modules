/** @odoo-module */

import { CashMovePopup } from "@point_of_sale/app/navbar/cash_move_popup/cash_move_popup";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";
import { CashMoveReceipt } from "@point_of_sale/app/navbar/cash_move_popup/cash_move_receipt/cash_move_receipt";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";

patch(CashMovePopup.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.savedMoneyDetails = null;
    },

    // --- Lógica de la Calculadora ---
    async openDetailsPopup() {
        try {
            const { confirmed, payload } = await this.popup.add(MoneyDetailsPopup, {
                moneyDetails: this.savedMoneyDetails, 
            });

            if (confirmed) {
                this.savedMoneyDetails = payload.moneyDetails;
                
                if (payload.total !== undefined) {
                    this.state.amount = payload.total.toFixed(2);
                }

                // Generar el texto detallado para el Motivo
                try {
                    const parts = [];

                    // 1. AGREGAMOS EL USUARIO AL TEXTO (Lo que pediste)
                    const cashier = this.pos.get_cashier();
                    if (cashier && cashier.name) {
                        parts.push(`Usuario: ${cashier.name}`);
                        parts.push('----------------'); 
                    }

                    let billsCopy = [...(this.pos.bills || [])];
                    billsCopy.sort((a, b) => b.value - a.value);

                    for (const bill of billsCopy) {
                        // Buscamos la cantidad
                        let qty = 0;
                        if (payload.moneyDetails) {
                            qty = payload.moneyDetails[bill.value] || payload.moneyDetails[String(bill.value)];
                        }

                        if (qty > 0) {
                            const valueStr = this.env.utils.formatCurrency(bill.value);
                            
                            // USAMOS EL NUEVO CAMPO 'money_type'
                            let typeName = "unidades";
                            if (bill.money_type === 'bill') typeName = "billetes";
                            if (bill.money_type === 'coin') typeName = "monedas";

                            // Formato: "3 billetes de $ 500.00"
                            parts.push(`${qty} ${typeName} de ${valueStr}`);
                        }
                    }

                    if (parts.length > 0) {
                        this.state.reason = parts.join('\n');
                    }
                } catch (err) {
                    console.error("Error texto:", err);
                }
            }
        } catch (e) {
            console.error("Error popup:", e);
        }
    },

    // --- Override del Confirmar para enviar datos extras al Recibo ---
    async confirm() {
        const amount = parseFloat(this.state.amount);
        const formattedAmount = this.env.utils.formatCurrency(amount);
        if (!amount) {
            this.notification.add(_t("Cash in/out of %s is ignored.", formattedAmount), 3000);
            return this.props.close();
        }

        const type = this.state.type;
        const translatedType = _t(type);
        const reason = this.state.reason.trim();
        
        // Llamada al backend (original)
        await this.orm.call("pos.session", "try_cash_in_out", [
            [this.pos.pos_session.id],
            type,
            amount,
            reason,
            { formattedAmount, translatedType },
        ]);

        await this.pos.logEmployeeMessage(
            `${_t("Cash")} ${translatedType} - ${_t("Amount")}: ${formattedAmount}`,
            "CASH_DRAWER_ACTION"
        );

        // --- DATOS NUEVOS PARA EL RECIBO ---
        
        // 1. Cajero (Apertura)
        const sessionOpener = this.pos.pos_session.user_id ? this.pos.pos_session.user_id[1] : "Desconocido";

        // 2. Responsable (Actual)
        const currentResponsable = this.pos.get_cashier() ? this.pos.get_cashier().name : "Desconocido";
        
        // 3. Nombre de la Caja (IMPORTANTE: Esto faltaba para que salga en el recibo)
        const posName = this.pos.config.name; 

        // Imprimir recibo personalizado
        await this.printer.print(CashMoveReceipt, {
            reason,
            translatedType,
            formattedAmount,
            headerData: this.pos.getReceiptHeaderData(),
            date: new Date().toLocaleString(),
            // Props extras
            sessionOpener: sessionOpener,
            responsable: currentResponsable,
            isCashOut: type === 'out',
            posName: posName // Enviamos el nombre de la caja
        });

        this.props.close();
        this.notification.add(
            _t("Successfully made a cash %s of %s.", type, formattedAmount),
            3000
        );
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