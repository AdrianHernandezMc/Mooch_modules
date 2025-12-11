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

    onClickButton(type) {
        this.state.type = type;
        try {
            if (this.inputRef && this.inputRef.el) {
                this.inputRef.el.focus();
            }
        } catch (e) {}
    },

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

                try {
                    const parts = [];

                    // Responsable actual en el texto
                    const currentCashier = this.pos.get_cashier();
                    if (currentCashier && currentCashier.name) {
                        parts.push(`Responsable retiro: ${currentCashier.name}`);
                        parts.push('----------------');
                    }

                    let billsCopy = [...(this.pos.bills || [])];
                    billsCopy.sort((a, b) => b.value - a.value);

                    for (const bill of billsCopy) {
                        let qty = 0;
                        if (payload.moneyDetails) {
                            qty = payload.moneyDetails[bill.value] || payload.moneyDetails[String(bill.value)];
                        }

                        if (qty > 0) {
                            const valueStr = this.env.utils.formatCurrency(bill.value);
                            let typeName = "unidades";
                            if (bill.money_type === 'bill') typeName = "billetes";
                            if (bill.money_type === 'coin') typeName = "monedas";
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

    async confirm() {
        const amount = parseFloat(this.state.amount);
        const formattedAmount = this.env.utils.formatCurrency(amount);
        if (!amount) {
            this.notification.add(_t("Monto inválido"), 3000);
            return this.props.close();
        }

        const type = this.state.type;
        const translatedType = _t(type);
        const reason = this.state.reason.trim();
        
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

        // =======================================================
        // LÓGICA DE NOMBRES
        // =======================================================

        // --- 1. RESPONSABLE ACTUAL---
        const currentCashier = this.pos.get_cashier();
        const currentResponsable = currentCashier ? currentCashier.name : "Desconocido";


        // --- 2. CAJERO DE APERTURA (Permisos Básicos) ---
        let sessionOpener = "Desconocido";

        // Obtenemos la configuración de esta caja
        const config = this.pos.config;

        // Verificamos si hay empleados configurados en "Permisos básicos"
        if (config.basic_employee_ids && config.basic_employee_ids.length > 0) {
            const basicEmployeeId = config.basic_employee_ids[0];
            const basicEmployee = this.pos.employees.find(emp => emp.id === basicEmployeeId);

            if (basicEmployee) {
                sessionOpener = basicEmployee.name;
            }
        }

        // Fallback: Si no hay nadie en permisos básicos
        if (sessionOpener === "Desconocido") {
             if (this.pos.pos_session.user_id) {
                 sessionOpener = this.pos.pos_session.user_id[1];
             }
        }
        // =======================================================

        const posName = this.pos.config.name;

        // --- CORRECCIÓN AQUÍ: Definimos receiptData ANTES de usarlo ---
        const receiptData = {
            reason,
            translatedType,
            formattedAmount,
            headerData: this.pos.getReceiptHeaderData(),
            date: new Date().toLocaleString(),
            sessionOpener: sessionOpener,
            responsable: currentResponsable,
            isCashOut: type === 'out',
            posName: posName
        };

        // Primera copia (Usando la variable receiptData)
        await this.printer.print(CashMoveReceipt, receiptData);

        // Segunda copia (Usando la variable receiptData)
        await this.printer.print(CashMoveReceipt, receiptData);

        this.props.close();
        this.notification.add(
            _t("Transacción exitosa: %s - %s", translatedType, formattedAmount),
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