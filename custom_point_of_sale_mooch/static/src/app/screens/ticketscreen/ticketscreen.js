/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { MaskedInputPopup } from "@custom_point_of_sale_mooch/app/popup/masked_input_popup"
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { useService } from "@web/core/utils/hooks";
import { useState, onMounted } from "@odoo/owl";
import { Order } from "@point_of_sale/app/store/models";

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
        (async () => {
            let searchOrder;
            while (!searchOrder) {
                const { confirmed, payload } = await this.popup.add(MaskedInputPopup, {
                    title: "Buscar orden",
                    body: "Ingresa el número de orden",
                });

                if (!confirmed) {
                    console.log("Popup cancelado");
                    return; 
                }

                const receiptNumber = "Orden " + payload?.trim();
                if (!receiptNumber) continue; // si no escribe nada, vuelve a mostrar el popup
                //obtengo la lista de las ordenes
                const result = await this.get_all_synced_orders();
                //filtro mi orden capturada
                searchOrder  = result.find(order => order.name === receiptNumber);
                //ubico la pagina de la orden
                const index = result.findIndex(order => order.name === receiptNumber);    
                const nPerPage = this._state.syncedOrders.nPerPage;
                const page = Math.floor(index / nPerPage) + 1;

                this._state.syncedOrders.currentPage = page;
                
                await this._fetchSyncedOrders();
                //***************************************** */    
                if (!searchOrder ) {
                    await this.popup.add(ErrorPopup, {
                        title: "No encontrada",
                        body: `No existe una orden con el número ${receiptNumber}`,
                    });
                }
            }

            console.log("oncilck")
            this.onClickOrder(searchOrder);
            this.clearRefundlines();
            this.render?.();
        })();
        });
    },

    async get_all_synced_orders() {
        const domain = this._computeSyncedOrdersDomain();
        const config_id = this.pos.config.id;

        this._state.syncedOrders.currentPage = 1
        const offset = (this._state.syncedOrders.currentPage - 1) * this._state.syncedOrders.nPerPage;

        // Llamamos sin limit ni offset para traer todas las órdenes
        const { ordersInfo } = await this.orm.call(
            "pos.order",
            "search_paid_order_ids",
            [],
            { config_id, domain, limit: 1000000, offset }
        );

        const ids = ordersInfo.map(info => info[0]);
        if (!ids.length) return [];

        let fetchedOrders = await this.orm.call("pos.order", "export_for_ui", [ids]);

        await this.pos._loadMissingProducts(fetchedOrders);
        await this.pos._loadMissingPartners(fetchedOrders);

        fetchedOrders = fetchedOrders.map(o => new Order({ env: this.env }, { pos: this.pos, json: o }));
        return fetchedOrders; // 🔹 Devuelve todas las órdenes completas
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

    async onClickOrder(order) {
        _superOnClickOrder.apply(this, arguments);
        this.clearRefundlines()
        const orderBackendId = order.backendId

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

        order.voucher_code = pos_voucher_code[0]?.code
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

        refundLines.forEach(l => {
            l.refunded_qty += l.changes;   // refleja el cambio en memoria
            l.changes = 0;
            delete this.pos.toRefundLines?.[l.id];
        });

        this.render();
    },
})