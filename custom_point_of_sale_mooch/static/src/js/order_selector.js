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
        //console.log("changesxx",this.changes)
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
        //alert("entro2")
        const json = super.export_as_JSON(...arguments);
        json.changes = this.changes || [];
        return json;
    },

    /**
     * 4) API de conveniencia para el front-end.
     */
    addChange(change) {
        //alert("entro3")
        this.changes.push(change);
        this.trigger("change", { changes: this.changes });
    },
});



const _superOnClickOrder = TicketScreen.prototype.onClickOrder;
const _superSetup = TicketScreen.prototype.setup;

patch(TicketScreen.prototype, {
    setup() {
        this.orm = useService("orm");
        _superSetup.apply(this, arguments);
    },

    async onClickOrder(order) {
        //console.log("Order",order)
        _superOnClickOrder.apply(this, arguments);
        
        const refundLines = order.get_orderlines().filter(l => l.changes > 0);
        if (!refundLines.length) {
            this.render();
            return;
        }

        //console.log("refundLines",refundLines)
        //const lineIds = refundLines.map(l => l.id); 
        //console.log("lineIds",lineIds)       
        
        
        //const qtys    = refundLines.map(l => l.changes);   

        // await this.orm.call(
        //     "pos.order.line",          // modelo
        //     "action_simple_refund",    // método
        //     [lineIds, qtys],           // *args*
        //     {}                         // *kwargs* (vacío si no usas)
        // );

        // 5. Actualiza la vista localmente
        refundLines.forEach(l => {
            l.refunded_qty += l.changes;   // refleja el cambio en memoria
            l.changes = 0;
            delete this.pos.toRefundLines?.[l.id];
        });
        this.render();
    },
  });







//           /** @odoo-module **/
// import { patch }    from '@web/core/utils/patch';
// import { TicketScreen } from '@point_of_sale/app/screens/ticket_screen/ticket_screen';
//
// const _superSetOrder = TicketScreen.prototype._setOrder;
// alert("entro order")
// patch(TicketScreen, {
//    async loadOrder(orderUid) {
//      alert("entro")
//     const result = super.selectOrder(order);
//
//     // 2) Tu lógica: por ejemplo, rellenar toRefundLines
//     this.pos.toRefundLines = this.pos.toRefundLines || {};
//     const current = this.pos.get_order();
//     current.get_orderlines().forEach(line => {
//       if (line.changes > 0) {
//         this.pos.toRefundLines[line.id] = {
//           orderline: line,
//           qty:        line.changes,
//         };
//       }
//     });
//
//     return result;
//   },
// });