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

        /******************* PRIMERO OBTENER Y DEBUGGEAR LOS CHANGES_CODES *******************/
        let pos_changes = await this.orm.call(
            "pos.changes",          
            "search_read",          
            [[["dest_id", "=", orderBackendId]]], 
            { fields: ["default_code", "origin_reference"] }
        );     
        
        console.log("🔧 Resultado de pos_changes:", pos_changes);
        
        let changes_order = ""; 
        let change_codes = "";
        
        for (const rd of pos_changes) {
            console.log("🔧 Registro de cambio:", rd);
            change_codes = change_codes + " - [" + (rd.default_code || '') + "]";
            changes_order = rd.origin_reference || changes_order;
        }
        
        change_codes = " " + changes_order + " " + change_codes;
        order.changes_codes = change_codes;
        
        console.log(`🔧 changes_order: '${changes_order}'`);
        console.log(`🔧 change_codes: '${change_codes}'`);
        console.log(`🔧 changes_codes final: '${order.changes_codes}'`);

        /******************* ANALIZAR DESCUENTO GLOBAL DE LA ORDEN *******************/
        console.log("🔧 Analizando descuento global de la orden...");
        
        // Analizar si la orden tiene descuento global
        const discountAnalysis = this.analyzeOrderGlobalDiscount(order);
        order.hasGlobalDiscount = discountAnalysis.hasGlobalDiscount;
        order.globalDiscountPercentage = discountAnalysis.discountPercentage;
        order.globalDiscountFactor = discountAnalysis.discountFactor;
        order.globalDiscountLines = discountAnalysis.discountLines;
        
        console.log(`🔧 Orden ${order.name} - Descuento global: ${order.hasGlobalDiscount ? order.globalDiscountPercentage + '%' : 'NO'}`);
        
        /******************* 🎯 GUARDAR EN CACHE DEL POS PARA PRODUCTSCREEN 🎯 *******************/
        // Inicializar el cache si no existe
        if (!this.pos.originalOrderDiscountInfo) {
            this.pos.originalOrderDiscountInfo = {};
        }
        
        // Extraer el número de orden (00037-354-0006)
        const orderNumber = order.name.replace('Orden ', '');
        
        // 🎯 GUARDAR CON MÚLTIPLES FORMATOS PARA ASEGURAR COINCIDENCIA
        const cacheData = {
            hasGlobalDiscount: discountAnalysis.hasGlobalDiscount,
            discountPercentage: discountAnalysis.discountPercentage,
            discountFactor: discountAnalysis.discountFactor,
            originalOrderName: order.name,
            analyzedAt: new Date().toISOString()
        };

        // Formato 1: Nombre completo de la orden
        this.pos.originalOrderDiscountInfo[order.name] = cacheData;
        console.log(`🔧 💾 Guardado con clave: '${order.name}'`);

        // Formato 2: Solo el número (00037-354-0006)
        this.pos.originalOrderDiscountInfo[orderNumber] = cacheData;
        console.log(`🔧 💾 Guardado con clave: '${orderNumber}'`);

        // Formato 3: Con "Ord: " prefix (como aparecerá en ProductScreen)
        const ordPrefixKey = `Ord: ${orderNumber}`;
        this.pos.originalOrderDiscountInfo[ordPrefixKey] = cacheData;
        console.log(`🔧 💾 Guardado con clave: '${ordPrefixKey}'`);

        // Formato 4: changes_codes completo (si no está vacío)
        if (change_codes && change_codes.trim() !== "" && change_codes !== " ") {
            this.pos.originalOrderDiscountInfo[change_codes] = cacheData;
            console.log(`🔧 💾 Guardado con clave: '${change_codes}'`);
        }

        // Formato 5: changes_codes con formato de ProductScreen
        const productScreenFormat = `Ord: ${orderNumber} Codes: ${change_codes}`;
        this.pos.originalOrderDiscountInfo[productScreenFormat] = cacheData;
        console.log(`🔧 💾 Guardado con clave: '${productScreenFormat}'`);

        console.log(`🔧 💾 INFORMACIÓN DE DESCUENTO GUARDADA EN CACHE`);
        console.log(`🔧 💾 Descuento: ${discountAnalysis.discountPercentage}%`);
        console.log(`🔧 💾 Total de claves guardadas:`, Object.keys(this.pos.originalOrderDiscountInfo).length);
        console.log(`🔧 💾 Cache completo:`, this.pos.originalOrderDiscountInfo);
        
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

    /**
     * Analiza si una orden tiene descuento global directamente desde los datos en memoria
     */
    analyzeOrderGlobalDiscount(order) {
        try {
            const orderLines = order.get_orderlines();
            console.log(`🔧 Analizando ${orderLines.length} líneas en memoria para descuento global`);
            
            // Buscar líneas de descuento global
            const discountLines = orderLines.filter(line => 
                this.isGlobalDiscountLine(line)
            );

            console.log(`🔧 ${discountLines.length} líneas de descuento global encontradas en memoria`);

            let hasGlobalDiscount = false;
            let discountPercentage = 0;
            let discountFactor = 1;

            if (discountLines.length > 0) {
                // Calcular totales directamente desde las líneas en memoria
                const linesWithoutDiscount = orderLines.filter(line => 
                    !this.isGlobalDiscountLine(line) && !this.isDiscountOrRewardLine(line)
                );
                
                const totalSinDescuento = linesWithoutDiscount.reduce((sum, line) => {
                    const lineTotal = line.get_display_price() * Math.abs(line.quantity);
                    return sum + lineTotal;
                }, 0);
                
                const totalConDescuento = order.get_total_with_tax();
                
                console.log(`🔧 Total sin descuento: ${totalSinDescuento}, Total con descuento: ${totalConDescuento}`);
                
                if (totalSinDescuento > 0 && totalConDescuento < totalSinDescuento) {
                    discountPercentage = ((1 - (totalConDescuento / totalSinDescuento)) * 100);
                    discountFactor = totalConDescuento / totalSinDescuento;
                    
                    console.log(`🔧 Descuento calculado en memoria: ${discountPercentage.toFixed(2)}% (factor: ${discountFactor.toFixed(4)})`);
                    
                    // Considerar que tiene descuento global si es mayor a 1%
                    hasGlobalDiscount = discountPercentage > 1;
                }
            }

            return {
                hasGlobalDiscount,
                discountPercentage,
                discountFactor,
                discountLines
            };

        } catch (error) {
            console.error("🔧 Error analizando descuento global en memoria:", error);
            return {
                hasGlobalDiscount: false,
                discountPercentage: 0,
                discountFactor: 1,
                discountLines: []
            };
        }
    },

    /**
     * Verifica si una línea es un descuento global
     */
    isGlobalDiscountLine(line) {
        const productName = (line.product?.display_name || line.full_product_name || '').toLowerCase();
        const isDiscountProduct = productName.includes('descuento') || 
                                productName.includes('discount') ||
                                productName.includes('global') ||
                                productName.includes('general');
        
        // También verificar si el precio es negativo (característica de líneas de descuento)
        const isNegativePrice = line.get_unit_price() < 0;
        
        return isDiscountProduct || isNegativePrice;
    },

    /**
     * Verifica si una línea es de descuento o recompensa
     */
    isDiscountOrRewardLine(line) {
        const productName = (line.product?.display_name || line.full_product_name || '').toLowerCase();
        return productName.includes('descuento') || 
            productName.includes('reward') ||
            productName.includes('recompensa') ||
            productName.includes('discount') ||
            productName.includes('voucher') ||
            productName.includes('vale');
    },
})