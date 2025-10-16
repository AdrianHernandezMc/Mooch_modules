/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { useService } from "@web/core/utils/hooks";
import { useState, onMounted } from "@odoo/owl";

const _superOnClickOrder = TicketScreen.prototype.onClickOrder;
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
            //this.clearOrderlines()
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

    // async onDoRefund() {
    //     this.clearOrderlines() //** limpio todas las lineas de la orden acutal*/
    //     const selectedOrder = this.getSelectedOrder();
    //     const orderBackendId = selectedOrder.backendId; // o selectedOrder.id según tu flujo
    //     this.pos.TicketScreen_onDoRefund = false
        
    //     let method = await this.orm.call(
    //         "pos.payment",          
    //         "search_read",          
    //         [[["pos_order_id", "=", orderBackendId]]], 
    //         { fields: ["payment_method_id", "transaction_id"] }
    //     );

    //     const refundDetails = Object.values(this.pos.toRefundLines)
    //         .filter(d => d.qty > 0 && !d.destinationOrderUid);
        
    //     if (!refundDetails.length) {
    //       return alert("selecciona un articulo")
    //     }

    //     const totalRefundWithTax = refundDetails.reduce((acc, detail) => {
    //         const line = detail.orderline.price;
    //         return acc + (Math.round(((line*1.16) *100) /100)*-1);
    //     }, 0);

        
    //     if (method) {
    //         if (!method[0].transaction_id || method[0].transaction_id ==="" ) {
    //             this.pos.sharedtcode= 0 
    //             //alert(this.pos.sharedtcode)
    //         }
    //         else {
    //                 this.pos.sharedtcode = method[0].transaction_id
    //         }
            
    //         method = this.pos.payment_methods_by_id[method[0].payment_method_id[0]];
    //         const paymentline= this.pos.get_order().add_paymentline(method);
    //         paymentline.set_amount(totalRefundWithTax);
    //     }
    //     _superOnDoRefund.apply(this, arguments);
    //     // Activa bandera para validación automática
    //     this.pos.TicketScreen_onDoRefund = true;
    //     this.pos.showScreen("PaymentScreen") //, { autoValidate: true });
    // return
    //     //await this.validateOrder();
    //     //_superOnDoRefund.apply(this, arguments);
    // },

    async onClickOrder(order) {
        _superOnClickOrder.apply(this, arguments);
        this.clearRefundlines()

        const orderBackendId = order.backendId
        //console.log("order",order)

        /******************* agrego los codigos al producot  */
        let pos_changes = await this.orm.call(
            "pos.changes",          
            "search_read",          
            [[["dest_id", "=", orderBackendId]]], 
            { fields: ["default_code", "origin_reference"] }
        );     
        
        let changes_order = ""; 
        let change_codes = "";
        for (const rd of pos_changes) {
            change_codes = change_codes  + " - [" + rd.default_code + "]" || "";
            changes_order = rd.origin_reference;
        }
        
        change_codes = " "+ changes_order + " " + change_codes;
        order.changes_codes = change_codes;
        
        /** agreamos el codigo del vale al producto */
        let pos_voucher_code = await this.orm.call(
            "loyalty.card",          
            "search_read",          
            [[["source_pos_order_id", "=", orderBackendId]]], 
            { fields: ["code"] }
        ); 

        order.voucher_code = pos_voucher_code
        const addcode_to_orderline =  order.get_orderlines()
        addcode_to_orderline.forEach(l => {    
            if (!l.full_product_name.includes(l.product.barcode) && l.product.id !== order.product_changes_id && l.product.id !== order.product_voucher_id) {
                l.full_product_name = l.full_product_name + " - [" + l.product.barcode+"]";   // refleja el cambio en memoria
            }

            if (!l.full_product_name.includes(change_codes) && l.product.id == order.product_changes_id){
                l.full_product_name = l.full_product_name + change_codes
            }

            if (pos_voucher_code.length > 0){
                if (!l.full_product_name.includes(pos_voucher_code[0].code) && l.product.id == order.product_voucher_id){
                    
                     l.full_product_name = l.full_product_name + " - " + pos_voucher_code[0].code
                 } 
             }
        });

        const isRefund = order.orderlines.some(line => line.quantity < 0);

        if (isRefund) {
            this.pos.Sale_type = "Reembolso";
        }
        else {
            this.pos.Sale_type = null;   
        }

        
/// **** Echo para los camios de producto ********
        const refundLines = order.get_orderlines().filter(l => l.changes > 0);
        if (!refundLines.length) {
            this.render();
            return;
        } 

        // await this.orm.call(
        //     "pos.order.line",          // modelo
        //     "action_simple_refund",    // método
        //     [lineIds, qtys],           // *args*
        //     {}                         // *kwargs* (vacío si no usas)
        // );

        refundLines.forEach(l => {
            l.refunded_qty += l.changes;   // refleja el cambio en memoria
            l.changes = 0;
            delete this.pos.toRefundLines?.[l.id];
        });

        this.render();
    },
})