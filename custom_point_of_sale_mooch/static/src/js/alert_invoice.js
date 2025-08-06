/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { onMounted } from "@odoo/owl";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";

const _originalSetup = PaymentScreen.prototype.setup;

patch(PaymentScreen.prototype, {
    setup() {
        _originalSetup.apply(this, arguments);

        // 2) Al montar el componente, mostrar la alerta una sola vez
        onMounted(() => {
            const { confirmed } = this.popup.add(ConfirmPopup, {
            title: _t("Facturacion al cliente"),
            body: _t(
                "Favor de preguntar al cliente si necesita factura; si es así, registre los datos del cliente y la factura."
            ),
        });
        });
    },
});