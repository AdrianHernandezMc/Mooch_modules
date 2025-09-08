/** @odoo-module **/
import { registry } from "@web/core/registry";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { useService } from "@web/core/utils/hooks";
import { Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, {
    /**
     * 1) Cuando el servidor envía las líneas (load de sesión),
     *    los datos pasan por setup() → aquí inicializamos.
     */
    setup() {
        super.setup(...arguments);
        // Si viene de backend ya llegará como parte de props,
        // si es nueva línea aseguramos []
         this.changes = this.changes || [];
    },

    /**
     * 2) Cuando el POS vuelve a cargar un pedido guardado
     *    (ticket exchange, reimpresión…), se llama init_from_JSON.
     */
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.changes = json.changes || [];
    },

    /**
     * 3) Al enviar la orden al backend, añadimos el campo.
     */
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.changes = this.changes || [];
        return json;
    },

    /**
     * 4) API de conveniencia para el front-end.
     */
    addChange(change) {
        this.changes.push(change);
        this.trigger("change", { changes: this.changes });
    },
});