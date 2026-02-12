/** @odoo-module */

import { CashMovePopup } from "@point_of_sale/app/navbar/cash_move_popup/cash_move_popup";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";
import { CashMoveReceipt } from "@point_of_sale/app/navbar/cash_move_popup/cash_move_receipt/cash_move_receipt";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, useState } from "@odoo/owl"; 

patch(CashMovePopup.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.orm = useService("orm");
        this.printer = useService("printer");
        this.notification = useService("notification");
        this.popup = useService("popup");
        
        this.savedMoneyDetails = null;

        this.state = useState({
            ...this.state,
            cashInfo: {
                opening: 0,
                sales: 0,
                moves: 0,
                total: 0
            }
        });

        onWillStart(async () => {
            await this.calculateCashStatus();
        });
    },

    async calculateCashStatus() {
        try {
            const sessionId = this.pos.pos_session.id;

            // 1. OBTENER DATOS DE CIERRE DEL SERVIDOR (Total real)
            const sessionData = await this.orm.call(
                "pos.session",
                "get_closing_control_data",
                [[sessionId]]
            );

            // 2. EXTRAER VARIABLES
            const cashDetails = sessionData.default_cash_details || {};

            // A. TOTAL FINAL (La verdad absoluta según Odoo)
            // En tu log es 1592
            const total = cashDetails.amount || 0;
            
            // B. VENTAS (Pagos en efectivo registrados)
            // En tu log es 692
            const sales = cashDetails.payment_amount || 0;

            // C. FONDO INICIAL (Lo tomamos de la sesión local, que es más preciso para el desglose)
            // Debería ser 800
            const opening = this.pos.pos_session.cash_register_balance_start || 0;

            // D. MOVIMIENTOS (Entradas/Salidas manuales)
            // Calculamos por diferencia para que la suma sea perfecta:
            // Movimientos = Total - Fondo - Ventas
            // Ejemplo: 1592 - 800 - 692 = 100
            const moves = total - opening - sales;

            console.log("✅ DESGLOSE PERFECTO:", {
                Fondo: opening,
                Ventas: sales,
                Movimientos: moves,
                TOTAL_FINAL: total
            });

            // 3. ACTUALIZAR VISTA
            this.state.cashInfo = {
                opening: opening,
                sales: sales,
                moves: moves,
                total: total
            };

        } catch (error) {
            console.error("Error calculando balance:", error);
            this.state.cashInfo.total = 0; 
        }
    },

    fmt(value) {
        try {
            return this.env.utils.formatCurrency(value || 0, this.pos.currency);
        } catch (e) { return "0.00"; }
    },

    // --- Resto de métodos SIN CAMBIOS ---
    onClickButton(type) {
        this.state.type = type;
        if (this.inputRef && this.inputRef.el) this.inputRef.el.focus();
    },

    async openDetailsPopup() {
        try {
            const { confirmed, payload } = await this.popup.add(MoneyDetailsPopup, {
                moneyDetails: this.savedMoneyDetails,
            });
            if (confirmed) {
                this.savedMoneyDetails = payload.moneyDetails;
                if (payload.total !== undefined) this.state.amount = payload.total.toFixed(2);
                try {
                    const parts = [];
                    const currentCashier = this.pos.get_cashier();
                    if (currentCashier?.name) {
                        parts.push(`Responsable: ${currentCashier.name}`);
                        parts.push('----------------');
                    }
                    let billsCopy = [...(this.pos.bills || [])];
                    billsCopy.sort((a, b) => b.value - a.value);
                    for (const bill of billsCopy) {
                        let qty = 0;
                        if (payload.moneyDetails) qty = payload.moneyDetails[bill.value] || payload.moneyDetails[String(bill.value)];
                        if (qty > 0) {
                            const valStr = this.env.utils.formatCurrency(bill.value, this.pos.currency);
                            const typeName = bill.money_type === 'bill' ? "billetes" : "monedas";
                            parts.push(`${qty} ${typeName} de ${valStr}`);
                        }
                    }
                    if (parts.length > 0) this.state.reason = parts.join('\n');
                } catch(e){}
            }
        } catch (e) { console.error(e); }
    },

    async confirm() {
        const amount = parseFloat(this.state.amount);
        const formattedAmount = this.env.utils.formatCurrency(amount, this.pos.currency);
        if (!amount) {
            this.notification.add(_t("Monto inválido"), { type: "danger" });
            return;
        }
        const type = this.state.type;
        const translatedType = _t(type);
        const reason = this.state.reason ? this.state.reason.trim() : "";
        try {
            await this.orm.call("pos.session", "try_cash_in_out", [
                [this.pos.pos_session.id], type, amount, reason,
                { formattedAmount, translatedType },
            ]);
            const receiptData = {
                reason, translatedType, formattedAmount,
                headerData: this.pos.getReceiptHeaderData(),
                date: new Date().toLocaleString(),
                sessionOpener: this.pos.pos_session.user_id ? this.pos.pos_session.user_id[1] : "Sistema",
                responsable: this.pos.get_cashier() ? this.pos.get_cashier().name : "Desconocido",
                isCashOut: type === 'out',
                posName: this.pos.config.name
            };
            await this.printer.print(CashMoveReceipt, receiptData);
            await this.printer.print(CashMoveReceipt, receiptData);
            this.props.close();
            this.notification.add(_t("Movimiento exitoso"), { type: "success" });
        } catch (error) {
            console.error(error);
            this.notification.add(_t("Error procesando movimiento"), { type: "danger" });
        }
    }
});