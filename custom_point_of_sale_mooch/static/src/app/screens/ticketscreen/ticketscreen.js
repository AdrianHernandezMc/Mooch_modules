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
const _superOnClickTicketExchange = TicketScreen.prototype.onClickTicketExchange;

patch(TicketScreen.prototype, {
    setup() {
        this.pos = useService("pos");
        this.orm = useService("orm");

        if (!this.pos.sharedVar) {
            this.pos.sharedtcode = useState({ value: "" });
        }
        _superSetup.apply(this, arguments);

        // ✅ AGREGAR ESTADO PARA CONTROLAR EL BOTÓN
        this.state = useState({
            blockChangesForCurrentOrder: false
        });

        // 🔴 NUEVO: inicializar referencia a la orden seleccionada en TicketScreen
        this.selectedSyncedOrderForChange = null;

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
                    if (!receiptNumber) continue;

                    const result = await this.get_all_synced_orders();
                    searchOrder  = result.find(order => order.name === receiptNumber);
                    const index = result.findIndex(order => order.name === receiptNumber);
                    const nPerPage = this._state.syncedOrders.nPerPage;
                    const page = Math.floor(index / nPerPage) + 1;

                    this._state.syncedOrders.currentPage = page;

                    await this._fetchSyncedOrders();

                    if (!searchOrder ) {
                        await this.popup.add(ErrorPopup, {
                            title: "No encontrada",
                            body: `No existe una orden con el número ${receiptNumber}`,
                        });
                    }
                }

                console.log("oncilck")
                this.onClickOrder.call(this, searchOrder);
                this.clearRefundlines();
                this.render?.();
            })();
        });
    },

    /**
     * Verifica si la orden actual permite cambios
     * 🟢 AJUSTE: aceptamos opcionalmente una orden (por ejemplo, la seleccionada en TicketScreen)
     */
    canChangeProducts(orderFromTicket) {
        // Orden prioritaria: la que viene del TicketScreen, luego la que guardamos, luego la actual del POS
        const order = orderFromTicket || this.selectedSyncedOrderForChange || this.pos.get_order?.();

        if (!order) {
            console.log("🔧 canChangeProducts: sin orden, PERMITIENDO por defecto");
            return true;
        }

        // ✅ VERIFICAR MÚLTIPLES INDICADORES DE BLOQUEO
        const hasChangeCodes =
            order.changes_codes &&
            String(order.changes_codes).trim() !== "" &&
            String(order.changes_codes).trim() !== " ";

        const isBlocked =
            order.isReadOnly ||
            order.blockProductChanges ||
            this.pos.blockChangesForCurrentOrder ||
            hasChangeCodes;

        console.log(`🔧 Verificación cambios productos: ${isBlocked ? 'BLOQUEADO' : 'PERMITIDO'}`, {
            name: order.name,
            isReadOnly: order.isReadOnly,
            blockProductChanges: order.blockProductChanges,
            blockChangesForCurrentOrder: this.pos.blockChangesForCurrentOrder,
            changes_codes: order.changes_codes
        });

        return !isBlocked;
    },

    // 🔴 NUEVO: interceptar click en "Cambiar Articulos"
    async onClickTicketExchange(...args) {
        const order = this.selectedSyncedOrderForChange || this.pos.get_order?.();

        console.log(
            "🔧 onClickTicketExchange interceptado para:",
            order?.name,
            "changes_codes:",
            order?.changes_codes
        );

        const canChange = this.canChangeProducts(order);

        console.log("🔧 Resultado canChangeProducts en click:", canChange);

        if (!canChange) {
            await this.popup.add(ErrorPopup, {
                title: "Orden en modo consulta",
                body: "Esta orden ya tiene cambios registrados. Solo se permite consulta, no se pueden generar nuevos cambios.",
            });
            return; // 👈 NO llamamos al super → NO va al ProductScreen
        }

        // Si se permiten cambios, ejecutamos el comportamiento nativo
        return _superOnClickTicketExchange.apply(this, args);
    },

    async get_all_synced_orders() {
        const domain = this._computeSyncedOrdersDomain();
        const config_id = this.pos.config.id;

        this._state.syncedOrders.currentPage = 1;
        const offset = (this._state.syncedOrders.currentPage - 1) * this._state.syncedOrders.nPerPage;

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
        return fetchedOrders;
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

    /**
     * Verifica si la orden ya tiene cambios previos EN LA BASE DE DATOS
     */
    async hasExistingChanges(order) {
        try {
            console.log("🔧 Ejecutando hasExistingChanges...");

            const orderBackendId = order.backendId;

            // ✅ VERIFICACIÓN 1: Buscar en pos.changes si ya hay registros para esta orden
            let pos_changes = await this.orm.call(
                "pos.changes",
                "search_count",          // ✅ USAR search_count EN LUGAR DE search_read - MÁS RÁPIDO
                [[["dest_id", "=", orderBackendId]]]
            );

            const hasChangesInDB = pos_changes > 0;

            console.log(`🔧 Verificación BD: ${hasChangesInDB ? pos_changes + ' registros' : 'Sin cambios'}`);

            return hasChangesInDB;

        } catch (error) {
            console.error("🔧 Error verificando cambios existentes:", error);
            return false;
        }
    },

    async onClickOrder(order) {
        /******************* 🚫 VERIFICAR SI LA ORDEN YA TIENE CAMBIOS 🚫 *******************/
        console.log("🔧 Verificando si la orden ya tiene cambios previos...");

        // 🔴 NUEVO: guardar la orden seleccionada en TicketScreen
        this.selectedSyncedOrderForChange = order;

        // ✅ VERIFICAR SI LA ORDEN YA TIENE CAMBIOS
        const hasChanges = await this.hasExistingChanges(order);
        console.log(`🔧 Resultado verificación cambios: ${hasChanges}`);

        if (hasChanges) {
            console.log("🚫 Orden ya tiene cambios previos, PERMITIENDO SOLO CONSULTA...");

            // ✅ OBTENER MÁS INFORMACIÓN SOBRE LOS CAMBIOS PARA EL MENSAJE
            let changeDetails = "";
            try {
                const orderBackendId = order.backendId;
                let pos_changes = await this.orm.call(
                    "pos.changes",
                    "search_read",
                    [[["dest_id", "=", orderBackendId]]],
                    { fields: ["default_code", "origin_reference", "create_date"] }
                );

                if (pos_changes && pos_changes.length > 0) {
                    changeDetails = `\n\nSe encontraron ${pos_changes.length} cambio(s) realizados.`;
                    if (pos_changes[0].create_date) {
                        const changeDate = new Date(pos_changes[0].create_date).toLocaleDateString();
                        changeDetails += `\nÚltimo cambio: ${changeDate}`;
                    }
                }
            } catch (error) {
                console.error("Error obteniendo detalles de cambios:", error);
            }

            await this.popup.add(ErrorPopup, {
                title: "📋 Orden con cambios existentes - MODO CONSULTA",
                body: `La orden ${order.name} ya tiene cambios realizados. Puedes VER los productos pero NO realizar cambios adicionales.${changeDetails}`,
            });

            // ✅ PERMITIR VER LA ORDEN PERO BLOQUEAR CAMBIOS
            this.clearRefundlines();

            // ✅ CARGAR LA ORDEN EN MODO SOLO LECTURA
            _superOnClickOrder.apply(this, arguments);
            await this.processOrderDetails(order, true); // true = modo solo lectura

            // ✅ MARCAR LA ORDEN COMO SOLO LECTURA EN EL POS
            if (this.pos.get_order()) {
                this.pos.get_order().isReadOnly = true;
            }

            return;
        }

        /******************* CONTINUAR CON EL PROCESO NORMAL *******************/
        _superOnClickOrder.apply(this, arguments);
        this.clearRefundlines();
        await this.processOrderDetails(order, false); // false = modo normal (permite cambios)
    },

    /**
     * Procesa los detalles de la orden (compartido entre modo normal y solo lectura)
     */
    async processOrderDetails(order, isReadOnly = false) {
        const orderBackendId = order.backendId;

        // ✅ MARCAR EXPLÍCITAMENTE LA ORDEN COMO SOLO LECTURA
        if (isReadOnly) {
            order.isReadOnly = true;
            console.log("🔧 🚫 ORDEN EN MODO SOLO LECTURA - NO SE PERMITEN CAMBIOS");
        }

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
            isReadOnly: isReadOnly, // ✅ GUARDAR SI ES SOLO LECTURA
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
        console.log(`🔧 💾 Modo solo lectura: ${isReadOnly}`);
        console.log(`🔧 💾 Total de claves guardadas:`, Object.keys(this.pos.originalOrderDiscountInfo).length);

        /** agreamos el codigo del vale al producto */
        let pos_voucher_code = await this.orm.call(
            "loyalty.card",
            "search_read",
            [[["source_pos_order_id", "=", orderBackendId]]],
            { fields: ["code"] }
        );

        order.voucher_code = pos_voucher_code[0]?.code;
        const addcode_to_orderline =  order.get_orderlines();
        addcode_to_orderline.forEach(l => {
            if (!l.full_product_name.includes(l.product.barcode) && l.product.id !== order.product_changes_id && l.product.id !== order.product_voucher_id) {
                l.full_product_name = l.full_product_name + " - [" + l.product.barcode+"]";
            }

            if (!l.full_product_name.includes(change_codes) && l.product.id == order.product_changes_id){
                l.full_product_name = l.full_product_name + change_codes;
            }

            if (pos_voucher_code.length > 0){
                if (!l.full_product_name.includes(pos_voucher_code[0].code) && l.product.id == order.product_voucher_id){
                    l.full_product_name = l.full_product_name + " - " + pos_voucher_code[0].code;
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

        // ✅ EN MODO SOLO LECTURA, LIMPIAR CUALQUIER LÍNEA DE CAMBIO
        if (isReadOnly) {
            console.log("🔧 🚫 Modo solo lectura - Limpiando líneas de cambio");
            const refundLines = order.get_orderlines().filter(l => l.changes > 0);
            refundLines.forEach(l => {
                l.changes = 0;
                delete this.pos.toRefundLines?.[l.id];
            });

            // ✅ LIMPIAR toRefundLines COMPLETAMENTE
            this.pos.toRefundLines = {};
        } else {
            /// **** Procesar cambios de producto (solo en modo normal) ********
            const refundLines = order.get_orderlines().filter(l => l.changes > 0);
            if (!refundLines.length) {
                this.render();
                return;
            }

            refundLines.forEach(l => {
                l.refunded_qty += l.changes;
                l.changes = 0;
                delete this.pos.toRefundLines?.[l.id];
            });
        }

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
});