/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { onMounted } from "@odoo/owl";

// Guardamos el setup original
const _originalSetup = PaymentScreen.prototype.setup;

patch(PaymentScreen.prototype, {
    setup() {
        // 1) Llamar al setup original
        _originalSetup.apply(this, arguments);

        // 2) Al montar el componente, mostrar la alerta una sola vez
        onMounted(() => {
            //console.log("hola mundo"); //  Este elemento estará disponible aquí
            alert("Favor de preguntar al cliente si necesita factura si es asi persiona en factura")
        });
    },
});