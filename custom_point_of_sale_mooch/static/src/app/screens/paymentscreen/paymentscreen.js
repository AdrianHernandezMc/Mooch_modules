/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useState } from "@odoo/owl";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup"; 
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { useService } from "@web/core/utils/hooks";

function addMonthtoday(date = new Date()) {
    const y = date.getFullYear();
    const m = date.getMonth();  // 0=Ene
    const d = date.getDate();
    const targetM = m + 1;
    const targetY = y + Math.floor(targetM / 12);
    const targetMi = targetM % 12;
    const daysInTarget = new Date(targetY, targetMi + 1, 0).getDate(); // último día del mes destino
    const day = Math.min(d, daysInTarget);
return new Date(targetY, targetMi, day);
}

patch(PaymentScreen.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.pos.txState = useState({ value: "" });
        this.orm = useService("orm");
        this.rpc = useService("rpc");
    },
    async onMounted() {
        //this._super();
        // TicketScreen_onDoRefund bandera que proviene de point_of_sale_mooch.TicketScreen_onDoRefund
        if (this.pos.TicketScreen_onDoRefund){
            const line = this.selectedPaymentLine;
            line.transaction_id = String(this.pos.sharedtcode);
            this.render();
            this.autoValidate?.();
        }

        this.pos.TicketScreen_onDoRefund= false;

        if (this.pos.Reembolso) {
            this.validateOrder()
        } 

        if (this.pos.Reembolso== false && this.pos.TicketScreen_onDoRefund== false) {
            const { confirmed } = this.popup.add(ErrorPopup, {
                title: _t("Facturacion al cliente"),
                body: _t("Recordar al cliente que la facturación se realiza el mismo día."),
            });
        }
    },

    async autoValidate() {
        return await this.validateOrder();
    },

    get selectedPaymentLine() {
        return this.pos.get_order()?.selected_paymentline || null;
    },

    //  Requisito: si el nombre del método contiene 'Tarjeta de crédito' o 'Tarjeta de débito'
    get requiresTxId() {
        const line = this.selectedPaymentLine;
        const method = line?.payment_method;

        if (!method) return false;

        return !!method.require_transaction_id;
    },

    onTxInput(ev) {
        const val = ev.target.value.trim();
        this.pos.txState.value = val;
        const line = this.selectedPaymentLine;
        if (line) {
            line.transaction_id = val;
        }
    },


    async validateOrder() {
        // Bloquea validación si hace falta y no se capturó t.credito t.de
        
        

        const line = this.selectedPaymentLine;
        if (this.requiresTxId && (!line?.transaction_id || !line.transaction_id.trim())) {
            await this.popup.add(ErrorPopup, {
                title: _t("Falto caputrar id de la tajeta"),
                body: _t("Captura el Transaction ID para pagos con tarjeta."),
            });
            return;
        }

        // bloque para mover los cambios de los articulos *****
        const order = this.pos.get_order();
        console.log("Order",order.product_changes_id)
        const order_iines = order.get_orderlines();
        const cfgId = this.pos.config.id;
        const product_id = order.product_changes_id //await this.orm.call("pos.config", "get_changes_product_id", [cfgId], {});
        //console.log("Entro",await this.orm.call("pos.config", "get_changes_product_id", [cfgId], {}))
        const existe = order_iines.some(line => line.product.id === product_id);
        
        
        if (existe) {
            const ondoInventory = await this.apply_changes();
            if (!ondoInventory) {
               return
            }
        }
        // ************************************************
        
        /********* Agrego el vale al programa */
        const exist_vale = order_iines.some(line => line.product.id === order.product_voucher_id);

         if (!exist_vale) {
            this.currentOrder.couponPointChanges = []
         } 
        
        super.validateOrder(...arguments);
        console.log("Entro")

        // if (exist_vale) {
        //     alert("Entro")
        //     const crate_vale = this.create_vale(orderbeforebackend,loyalty_program_id)
        //     if (!crate_vale) {
        //         alert("error_vale")
        //        return
        //     }
        // }
    },

    async create_vale(order,loyaty_program_id){
    try {
        const companyId = this.pos.company?.id;   // ← ID de la compañía
        const exp = addMonthtoday(new Date());
        const dateAddOneMonth = exp.toISOString().slice(0, 10); // "YYYY-MM-DD"
        const partner = order.client;
        const lines = (order?.get_orderlines?.() || []).filter(
            (l) => l?.product?.id === order.product_voucher_id
        );

        let totalWithTax = (lines || []).reduce((acc, l) => {
            const p = l.get_all_prices?.();
            return acc + (p?.priceWithTax ?? 0);
        }, 0);
        totalWithTax = totalWithTax.toFixed(2);

        console.log("order",order.server_id)

        // Preparas el diccionario con todos los campos
        const couponData = {
          program_id:          loyaty_program_id,
          company_id:          companyId,                // compañía
          partner_id:          partner?.id || false,
          code:                order.voucher_code,
          expiration_date:     dateAddOneMonth,
          points:              totalWithTax,
          source_pos_order_id: order.server_id,         // referenciamos la venta
        };

        console.log("couponData",couponData)
        const couponId = await this.orm.create(
          "loyalty.card",    // modelo
          [ couponData ]     // aquí sí va un solo nivel de array
        );

        return false;

    } catch (err) {
         await this.popup.add(ErrorPopup, {
                title: "Error",
                body: err,
                confirmText: "OK",
            });
        return false;
    }

    },


    async apply_changes() {
        const details = Object.values(this.pos.toRefundLines);
        const refundDetails =  details.filter(d => d.qty > 0).map(d => d.orderline);
        const detallesArray = Object.values(refundDetails);

        if (!detallesArray.length) {
            alert("selecciona un articulo");
            return false
        }

        // reviso si hay un movimiento de salida o venta
        const backendId = detallesArray[0].orderBackendId; //ID de la venta que se va a aplicar el cambio.
        const res = await this.orm.call(
            "pos.order",
            "get_order_locations",
            [[backendId]]
        );

        const locations = res[backendId] || [];
        const firstLoc = locations[0];
        const order_name = await this.orm.call(
            "pos.order",
            "read",
            [[backendId]],
            { fields: ["name"] }
        );

        if (!firstLoc) {
            alert(`No hay movimiento de salida/venta en ${order_name[0].name}, ve a inventrio recepciones y valida el movimiento  ${order_name[0].name}`)
            return false
        }

        await this.save_tbl_changes(refundDetails);
        let ondoInventory = false
        ondoInventory =  await this.move_to_inventory(detallesArray, backendId,firstLoc)
        return ondoInventory
    },

     async save_tbl_changes(refundDetails) {
    //crea una lines de cambio en la tabla de cambios.
        const destinationOrder = this.pos.get_order();
        const origin_id = refundDetails.map(d => d.orderBackendId);
        const productId_origin =  refundDetails.map(d => d.productId);

        await this.orm.call(
            'pos.changes',
            'poschanges_links_pre',
            [
                origin_id[0],
                destinationOrder.uid,
                productId_origin,
            ]
        );
    // *****
     },

    async move_to_inventory(detallesArray, backendId,firstLoc) {
        // 5) Por cada línea, creo el picking de entrada
        for (const detail of detallesArray) {
            const productId = detail.productId;
            const qty = detail.qty;
            const newQty = qty; //*-1;

            // //5.0 Actualizo cada orderline en negativo
            const lineIds = await this.orm.call(
            'pos.order.line',     // modelo (string)
            'search',             // método (string)
            [[                    // args: array con tu dominio
                ['order_id',   '=', backendId],
                ['product_id', '=', productId],
            ]],
            {}                    // kwargs (objeto)
            );

            await this.orm.call(
                'pos.order.line',
                'write',
                [ lineIds, { changes: newQty } ],
                {}
            );

            // 5.1) UoM del producto
            const [prod] = await this.orm.call(
                "product.product",    // modelo
                "read",               // método
                [[productId], ["uom_id"]],
                {}
            );
            const uomId = prod.uom_id[0];

            // 5.2) Tipo de operación “incoming” para tu compañía
            const [pt] = await this.orm.call(
                "stock.picking.type",                    // modelo
                "search_read",                           // método
                [
                    [
                    ["code", "=", "incoming"],
                    ["warehouse_id.company_id", "=", this.pos.company.id],
                    ],
                ],                                        // args: [ [ domain tuples ] ]
                { fields: ["id"] }                       // kwargs
            );
            if (!pt) {
                alert("No existe un tipo de operación de entrada configurado.......");
                return false
            }

            // 5.3) Crear el picking
            const pickingVals = {
                origin: `POS Return ${backendId}`,
                picking_type_id: pt.id,
                location_id: firstLoc.origin_id,
                location_dest_id: firstLoc.location_id,
                move_ids_without_package: [
            [0, 0, {
                product_id: productId,
                product_uom_qty: qty,
                product_uom: uomId,
                name: "Devolución POS",
                location_id: firstLoc.origin_id ,
                location_dest_id: firstLoc.location_id,
                }],
            ],
            };

            const pickingId = await this.orm.call(
                "stock.picking",       // modelo
                "create",              // método
                [pickingVals],         // args
                {}                     // kwargs
            );

            // 5.4) Confirmar, reservar y validar
            await this.orm.call("stock.picking", "action_confirm",    [[pickingId]]);
            await this.orm.call("stock.picking", "action_assign",     [[pickingId]]);
            await this.orm.call("stock.picking", "button_validate",   [[pickingId]]);
      }
      return true
    }
});

