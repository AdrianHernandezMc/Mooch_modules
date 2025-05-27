/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { useService } from "@web/core/utils/hooks";
import { CreditTermsPopup } from "@custom_credit_mooch/js/popup_credit_terms";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup();
        this.popup = useService("popup");
    },

    async onClick() {
        const order = this.pos.get_order();
        const client = order.partner;

        if (!client) {
            await this.popup.add(CreditTermsPopup, {
                title: "Cliente requerido",
                body: "Debes seleccionar un cliente antes de vender a crédito.",
                months: [],
            });
            return;
        }

        const result = await this.popup.add(CreditTermsPopup, {
            title: "Meses de Crédito",
            body: "Selecciona a cuántos meses se diferirá el pago",
        });

        if (result.confirmed) {
            const credit_pm = this.pos.payment_methods.find(pm =>
                pm.name.toLowerCase().includes("crédito")
            );
            if (!credit_pm) {
                await this.popup.add(CreditTermsPopup, {
                    title: "Método no encontrado",
                    body: "No se encontró un método de pago de tipo crédito.",
                    months: [],
                });
                return;
            }
            const paymentline = order.add_paymentline(credit_pm);
            paymentline.set_amount(order.get_total_with_tax());
            paymentline.credit_months = result.months;
        }
    },
});
