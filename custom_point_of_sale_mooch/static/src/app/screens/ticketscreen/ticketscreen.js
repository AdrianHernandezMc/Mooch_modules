/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { useService } from "@web/core/utils/hooks";
import { useState, onMounted } from "@odoo/owl";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";


const _superSetup = TicketScreen.prototype.setup;
const _superOnDoRefund = TicketScreen.prototype.onDoRefund;

patch(TicketScreen.prototype, {
    setup() {
        this.pos = useService("pos");
        this.orm = useService("orm");

        if (!this.pos.sharedVar) {
            this.pos.sharedtcode = useState({ value: "" });
        }
        _superSetup.apply(this, arguments);
        
        onMounted(() => {
            this.clearRefundlines();
            this.clearOrderlines()
            this.render?.();
        });
    },

    async clearRefundlines() {
        this.pos.toRefundLines = {};
    },
    
    async clearOrderlines() {
        const order = this.pos.get_order?.();
        const lines = order.get_orderlines?.();

        if (order) {
            for ( let line of lines) {
               order.removeOrderline.call(order, line);
            }
        }
    },

    async onDoRefund() {
        const selectedOrder = this.getSelectedOrder();
        const orderBackendId = selectedOrder.backendId; // o selectedOrder.id según tu flujo
        this.pos.TicketScreen_onDoRefund = false
        
        let method = await this.orm.call(
            "pos.payment",          
            "search_read",          
            [[["pos_order_id", "=", orderBackendId]]], 
            { fields: ["payment_method_id", "transaction_id"] }
        );

        const refundDetails = Object.values(this.pos.toRefundLines)
            .filter(d => d.qty > 0 && !d.destinationOrderUid);
        
        if (!refundDetails.length) {
          return alert("selecciona un articulo")
        }

        const totalRefundWithTax = refundDetails.reduce((acc, detail) => {
            const line = detail.orderline.price;
            return acc + (Math.round(((line*1.16) *100) /100)*-1);
        }, 0);

         if (method) {
            this.pos.sharedtcode = method[0].transaction_id
            method = this.pos.payment_methods_by_id[method[0].payment_method_id[0]];
            const paymentline= this.pos.get_order().add_paymentline(method);
            paymentline.set_amount(totalRefundWithTax);
        }
        _superOnDoRefund.apply(this, arguments);
        // Activa bandera para validación automática
        this.pos.TicketScreen_onDoRefund = true;
        this.pos.showScreen("PaymentScreen") //, { autoValidate: true });
    return
        //await this.validateOrder();
        //_superOnDoRefund.apply(this, arguments);
    }

})