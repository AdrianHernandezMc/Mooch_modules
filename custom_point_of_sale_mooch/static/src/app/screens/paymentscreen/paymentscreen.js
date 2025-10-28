/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useState } from "@odoo/owl";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup"; 
import { useService } from "@web/core/utils/hooks";
import { Order } from "@point_of_sale/app/store/models";

// Import del popup's
import { HomeDeliveryPopup } from "../../popup/home_delivery_popup";
import { DeliveryConfirmationPopup } from "../../popup/delivery_confirmation_popup";

function addMonthtoday(date = new Date()) {
    const y = date.getFullYear();
    const m = date.getMonth();
    const d = date.getDate();
    const targetM = m + 1;
    const targetY = y + Math.floor(targetM / 12);
    const targetMi = targetM % 12;
    const daysInTarget = new Date(targetY, targetMi + 1, 0).getDate();
    const day = Math.min(d, daysInTarget);
    return new Date(targetY, targetMi, day);
}

// ✅ CORREGIDO: Patch para Order - SIN el nombre del patch
patch(Order.prototype, {
    setup() {
        super.setup(...arguments);  // ✅ Cambiado: super en lugar de this._super
        this._homeDeliveryData = null;
        this._homeBoxPopupShown = false;
    },

    set_home_delivery_data(data) {
        this._homeDeliveryData = {
            contact_name: data.contact_name || "",
            phone: data.phone || "",
            address: data.address || "",
            notes: data.notes || "",
            lat: data.lat || 0.0,
            lng: data.lng || 0.0,
            maps_url: data.maps_url || "",
        };
    },

    get_home_delivery_data() {
        return this._homeDeliveryData;
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);  // ✅ Cambiado: super en lugar de this._super
        json.home_delivery_data = this._homeDeliveryData || null;
        return json;
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);  // ✅ Cambiado: super en lugar de this._super
        this._homeDeliveryData = json.home_delivery_data || null;
    },
});

// ✅ CORREGIDO: Patch para PaymentScreen - SIN el nombre del patch
patch(PaymentScreen.prototype, {
    setup() {
        super.setup();  // ✅ Cambiado: super en lugar de this._super
        this.pos = usePos();
        this.pos.txState = useState({ value: "" });
        this.orm = useService("orm");
        this.rpc = useService("rpc");
    },

    async onMounted() {
        //const c= null
        //this.requiresTxId(c)
        if (this.pos.TicketScreen_onDoRefund){
            const line = this.selectedPaymentLine;
            line.transaction_id = String(this.pos.sharedtcode);
            this.render();
            this.autoValidate?.();
        }

        this.pos.TicketScreen_onDoRefund = false;

        if (this.pos.Reembolso) {
            this.validateOrder();
        }

        if (this.pos.Reembolso == false && this.pos.TicketScreen_onDoRefund == false) {
            await this.popup.add(ErrorPopup, {
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

    get requiresTxId() {
        const line = this.selectedPaymentLine;
        const method = line?.payment_method;

        if (!method) return false;
        return !!method.require_transaction_id;
    },

    requiresTextId(line){
        const method = line?.payment_method;
        //console.log("method",method)
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
        const order = this.pos.get_order();
        const paymentLines = order.get_paymentlines();
        let requireErro = false
        paymentLines.forEach(line => {
            console.log("transaction_id",line.transaction_id)
             console.log("required", this.requiresTextId(line))
             console.log("orderline",line)
            if (this.requiresTextId(line) && (!line?.transaction_id || !line.transaction_id.trim())) {
                console.warn(`:`, line);
                this.popup.add(ErrorPopup, {
                title: _t("Falto capturar id de "+ line?.name),
                body: _t("Captura el Transaction ID para pagos con tarjeta."),
            });
                requireErro = true
            }
        });
        if (requireErro) {
            return
        }

        // bloque para mover los cambios de los articulos
        const order_iines = order.get_orderlines();
        const product_id = order.product_changes_id;
        const existe = order_iines.some(line => line.product.id === product_id);

        if (existe) {
            const ondoInventory = await this.apply_changes();
            if (!ondoInventory) {
            return;
            }
        }

        /********* Agrego el vale al programa */
        const exist_vale = order_iines.some(line => line.product.id === order.product_voucher_id);

        if (!exist_vale) {
            this.currentOrder.couponPointChanges = [];
        }

        if (exist_vale) {
            const cfgId = this.pos.config.id;
            const loyalty_program_id = await this.orm.call("pos.config","get_loyalty_program_id", [cfgId], {});
            const crate_vale = await this.create_vale(order, loyalty_program_id);
            if (!crate_vale) {
                console.log("error_vale");
                return;
            }
        }

        // ✅ [NUEVO FLUJO] Mostrar confirmación de entrega ANTES del formulario
        try {
            const config = this.pos?.config;
            const currentOrder = this.pos?.get_order?.();

            console.log("[DEBUG] Home Delivery Check:", {
                configExists: !!config,
                isHomeBox: config?.is_home_box,
                currentOrder: !!currentOrder,
                alreadyShown: currentOrder?._homeBoxPopupShown
            });

            if (config && config.is_home_box && currentOrder && !currentOrder._homeBoxPopupShown) {
                console.log("[DEBUG] Showing Delivery Confirmation Popup");

                // 1. Primero mostrar popup de confirmación
                const confirmationResult = await this.popup.add(DeliveryConfirmationPopup, {
                    title: _t("Entrega a Domicilio"),
                });

                if (!confirmationResult) {
                    console.log("[DEBUG] User cancelled delivery confirmation");
                    return false; // Usuario canceló todo
                }

                if (!confirmationResult.confirmed) {
                    console.log("[DEBUG] User cancelled delivery flow");
                    return false; // Usuario canceló
                }

                if (confirmationResult.wantsDelivery) {
                    console.log("[DEBUG] User wants delivery - showing address form");

                    // 2. Mostrar popup de datos de entrega
                    const deliveryResult = await this.popup.add(HomeDeliveryPopup, {
                        title: _t("Datos para entrega"),
                        body: _t("Captura los datos del pedido de entrega:"),
                        order: currentOrder,
                        config: config,
                    });

                    if (!deliveryResult || !deliveryResult.confirmed) {
                        console.log("[DEBUG] User cancelled address form");
                        return false; // Usuario canceló el formulario de dirección
                    }

                    // Marcar como mostrado solo si completó la entrega
                    currentOrder._homeBoxPopupShown = true;
                    console.log("[DEBUG] Delivery address completed");

                } else {
                    console.log("[DEBUG] User skipped delivery - proceeding to payment");
                    // Usuario eligió "Saltar Entrega" - continuar al pago sin datos de entrega
                    currentOrder._homeBoxPopupShown = true; // Marcar para que no vuelva a preguntar
                }
            }
        } catch (err) {
            console.error("Error en flujo de entrega:", err);
            // Si hay error, continuar con el pago normal
        }

        // ✅ SOLO si el popup se confirmó o no era necesario, procesar el pago
        const result = await super.validateOrder(...arguments);
        return result;
    },

    async create_vale(order,loyaty_program_id){
        // Normalizar y validar datos antes del RPC para evitar errores de validación
        const companyId = this.pos.company?.id;   // ← ID de la compañía
        const exp = addMonthtoday(new Date());
        const dateAddOneMonth = exp.toISOString().slice(0, 10); // "YYYY-MM-DD"
        const partner = order.client;
        const lines = (order?.get_orderlines?.() || []).filter(
            (l) => l?.product?.id === order.product_voucher_id
        );

        // Calcular puntos como número (no string)
        let totalWithTax = (lines || []).reduce((acc, l) => {
            const p = l.get_all_prices?.();
            return acc + (p?.priceWithTax ?? 0);
        }, 0);
        totalWithTax = Number(totalWithTax) || 0;

        // Asegurar que exista un código (field 'code' es obligatorio en el modelo loyalty.card)
        let code = order.voucher_code || null;
        if (!code) {
            // Generar un código seguro por defecto para evitar la validación
            const sanitizedOrder = (order.name || order.uid || 'ORD').toString().replace(/\s+/g, '_');
            code = `VALE-${sanitizedOrder}-${Date.now().toString(36)}`;
            // Guardar en el objeto order para uso posterior (opcional)
            try { order.voucher_code = code; } catch (e) { /* noop */ }
        }

        const couponData = {
          program_id:      loyaty_program_id,
          company_id:      companyId,
          partner_id:      partner?.id || false,
          code:            code,
          expiration_date: dateAddOneMonth,
          points:          totalWithTax,
          pos_reference:   order.name,
        };

        console.log("couponData", couponData);

        try {
            const couponId = await this.orm.create("loyalty.card", [ couponData ]);
            console.log("coupon created", couponId);
            return true;
        } catch (err) {
            console.error("create_vale RPC error:", err);
            // Mostrar popup de error con información amigable
            await this.popup.add(ErrorPopup, {
                title: _t("Error al crear vale"),
                body: _t("No se pudo crear el vale en el servidor. Revisa los logs del servidor para más detalles."),
            });
            return false;
        }

    },

    async apply_changes() {
        const details = Object.values(this.pos.toRefundLines);
        const refundDetails = details.filter(d => d.qty > 0).map(d => d.orderline);
        const detallesArray = Object.values(refundDetails);

        if (!detallesArray.length) {
            alert("selecciona un articulo");
            return false;
        }

        const backendId = detallesArray[0].orderBackendId;
        const res = await this.orm.call("pos.order", "get_order_locations", [[backendId]]);
        const locations = res[backendId] || [];
        const firstLoc = locations[0];
        const order_name = await this.orm.call("pos.order", "read", [[backendId]], { fields: ["name"] });

        if (!firstLoc) {
            alert(`No hay movimiento de salida/venta en ${order_name[0].name}, ve a inventrio recepciones y valida el movimiento  ${order_name[0].name}`);
            return false;
        }

        await this.save_tbl_changes(refundDetails);
        return await this.move_to_inventory(detallesArray, backendId, firstLoc);
    },

    async save_tbl_changes(refundDetails) {
        const destinationOrder = this.pos.get_order();
        const origin_id = refundDetails.map(d => d.orderBackendId);
        const productId_origin = refundDetails.map(d => d.productId);

        await this.orm.call('pos.changes', 'poschanges_links_pre', [
            origin_id[0],
            destinationOrder.uid,
            productId_origin,
        ]);
    },

    async move_to_inventory(detallesArray, backendId, firstLoc) {
        for (const detail of detallesArray) {
            const productId = detail.productId;
            const qty = detail.qty;

            const lineIds = await this.orm.call('pos.order.line', 'search', [[
                ['order_id', '=', backendId],
                ['product_id', '=', productId],
            ]], {});

            await this.orm.call('pos.order.line', 'write', [lineIds, { changes: qty }], {});

            const [prod] = await this.orm.call("product.product", "read", [[productId], ["uom_id"]], {});
            const uomId = prod.uom_id[0];

            const [pt] = await this.orm.call("stock.picking.type", "search_read", [[
                ["code", "=", "incoming"],
                ["warehouse_id.company_id", "=", this.pos.company.id],
            ]], { fields: ["id"] });

            if (!pt) {
                alert("No existe un tipo de operación de entrada configurado");
                return false;
            }

            const pickingVals = {
                origin: `POS Return ${backendId}`,
                picking_type_id: pt.id,
                location_id: firstLoc.origin_id,
                location_dest_id: firstLoc.location_id,
                move_ids_without_package: [[0, 0, {
                    product_id: productId,
                    product_uom_qty: qty,
                    product_uom: uomId,
                    name: "Devolución POS",
                    location_id: firstLoc.origin_id,
                    location_dest_id: firstLoc.location_id,
                }]],
            };

            const pickingId = await this.orm.call("stock.picking", "create", [pickingVals], {});
            await this.orm.call("stock.picking", "action_confirm", [[pickingId]]);
            await this.orm.call("stock.picking", "action_assign", [[pickingId]]);
            await this.orm.call("stock.picking", "button_validate", [[pickingId]]);
        }
        return true;
    },

    addNewPaymentLine(paymentMethod) {        
        // Validar que el total de la venta sea mayor que 0
        const orderTotal = this.currentOrder.get_total_with_tax ? this.currentOrder.get_total_with_tax() : this.currentOrder.total;
        console.log("orderTotal",orderTotal)
        if (orderTotal <= 0) {
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t("No se puede agregar metodo de pago: Total de la orden debe se mayor a 0."),
            });
            return false;
        }
        const result = super.addNewPaymentLine(...arguments);
        return result;
    }
});