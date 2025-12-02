/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { TextInputPopup } from "@point_of_sale/app/utils/input_popups/text_input_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { useService } from "@web/core/utils/hooks";
import { HotkeyHelpPopup } from "@custom_point_of_sale_mooch/app/popup/productscreen_help";
import { markup, onMounted, useState } from "@odoo/owl";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { PasswordInputPopup } from "@custom_point_of_sale_mooch/app/popup/hide_passwordpopup";
import { MaskedInputPopup } from "@custom_point_of_sale_mooch/app/popup/masked_input_popup"
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";

const _superSetNumpadMode = ProductScreen.prototype.onNumpadClick;
const _super_getRefundableDetails = TicketScreen.prototype._getRefundableDetails;
const _super_prepareRefundOrderlineOptions = TicketScreen.prototype._prepareRefundOrderlineOptions 

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
        const popup = useService("popup");
        this.orm = useService("orm");
        this.posService = useService("pos");
        this.cashTotal = useState({ value: 0 });
        //subo la variable al posStore para que se pueda leen en order_receipt y en todos lados
        this.pos.bloqueodecaja = false;
        this.pos.Reembolso = false;
        this.pos.Sale_type = null;
        if (this.pos.couponPointChanges) this.pos.couponPointChanges = [];
        if (typeof this.sum_cash === 'function') {
            this.pos.sum_cash = async () => await this.sum_cash();
        }
        this.pos.get_cash_out = async () => await this.get_cash_out();


        // Alt + P limpias las lineas de la orden
        useHotkey("Alt+t", (ev) => {
            const order = this.pos.get_order?.();
            const lines = order.get_orderlines?.();

            if (order) {
                for ( let line of lines) {
                order.removeOrderline.call(order, line);
                }
            }
        });

         // ALT % ejecuta el descuento
        useHotkey("Alt+d", (ev) => {
            this.onNumpadClick("discount")
        });

        // ALT % ejecuta el descuento
        useHotkey("Alt+p", (ev) => {
          //  this.notification.add("Modo descuento activado", { type: "info" });
            this.onNumpadClick("price")
        });

        // Alt + h → muestra ayuda
        useHotkey("Alt+h", async (ev) => {
            const order = this.pos.get_order();

            await popup.add(HotkeyHelpPopup, {
                title: "📖 Ayuda de Atajos",
                body: markup(`
                    <div style="text-align:left;">
                    <p><b>Alt + H</b> → Ayuda</p>
                    <p><b>Alt + P</b> → Activa de precios</p>
                    <b><b>Alt + T</b> → Limpiar líneas de venta</p>
                    <p><b>Alt + D</b> → Activa descuento</p>
                    <p><b>Alt + G</b> → Activa ventas guardadas</p>
                    <p><b>Alt + O</b> → Abre Caja</p>
                    </div>`),
            });
        });

        // **************   para hacer pruebad en productscreen  *******************
        useHotkey("alt+x", (ev) => {

            //this.clear_client()

            const orden = this.pos.get_order()
            console.log(orden)
            const orderlines = orden.get_orderlines()
            console.log(orderlines)
            // const match = 'descuento';

            // const discountLines = orderlines.filter(line => {
            // // intentar obtener el nombre del producto de formas comunes
            // const prodName =
            //     (line.product && line.product.name) ||
            //     line.product_name ||
            //     line.name ||
            //     line.display_name ||
            //     '';

            // return typeof prodName === 'string' && prodName.toLowerCase().includes(match.toLowerCase());
            // });

            // console.log("discountLines",discountLines)

        });

        // Alt + g para entrar a las ordenes guardadas
        useHotkey("alt+g", (ev) => {
            this.pos.showScreen("TicketScreen");
        });

        useHotkey("alt+r", (ev) => {
            const order = this.pos.get_order();
            order.disabledRewards.clear();
            alert("limpio reward")
        });

        useHotkey("alt+o", async (ev) => {
            await this.openCashDrawer();
        });
    },

    async debugOrderSearch(orderNumber) {
        console.log("🔍 DEBUG: Buscando orden:", orderNumber);
        
        // Probar diferentes métodos de búsqueda
        const searchMethods = [
            { name: "Por name exacto", domain: [["name", "=", orderNumber]] },
            { name: "Por pos_reference exacto", domain: [["pos_reference", "=", `Orden ${orderNumber}`]] },
            { name: "Por pos_reference con ilike", domain: [["pos_reference", "ilike", orderNumber]] },
            { name: "Por ID", domain: [["id", "=", parseInt(orderNumber)]] }
        ];
        
        for (const method of searchMethods) {
            try {
                const result = await this.orm.call("pos.order", "search_read", [
                    method.domain,
                    ["id", "name", "pos_reference", "state"]
                ], { limit: 5 });
                
                console.log(`${method.name}:`, result);
            } catch (error) {
                console.error(`Error en ${method.name}:`, error);
            }
        }
    },

    async _getProductByBarcode(code) {
        // Ejecutar la lógica original
        const product = await super._getProductByBarcode(code);

        // Tu lógica adicional después de obtener el producto
        if (product && product.default_code) {
            if (!product.display_name.includes(product.default_code)){
                product.display_name = `${product.display_name} - [${product.default_code}]`;
            }
        }
        return product;
    },

    async createvale_screen(amount_total){
        if (amount_total > 0) {
            await this.popup.add(ErrorPopup, {
                title: "Error",
                body: "Para crear un vale el total debe ser un valor negativo",
                confirmText: "OK",
            });
            return
        }

        const { confirmed } = await this.popup.add(ConfirmPopup,{
            title: 'VALES/VOUCHER',
            body: '¿Deseas crear un VALE por la cantidad de : '+ Math.round(((amount_total) *100) /100) +' pesos?',
            confirmText: 'Sí',
            cancelText: 'No',
        });

        if (!confirmed) {
            return;
        }

        const defaults = await this.orm.call(
            'loyalty.card',
            'default_get',
            [ ['code'] ]
        );

        let total = Number(amount_total)
        if (total < 1){
            amount_total =  amount_total/1.16 * -1
        }

        //******* Agrego la linea del producto a la pantalla de productos de venta. */
        const order   = this.currentOrder;
        const cfgId = this.pos.config.id;
        const loyalty_program_id = await this.orm.call("pos.config","get_loyalty_program_id", [cfgId], {});
        const product_id = await this.orm.call(
            "loyalty.reward", "search_read",
            [[["program_id", "=", loyalty_program_id]]],
            { fields: ["discount_line_product_id"] }
        );

        order.voucher_code = defaults.code
        let product = this.pos.db.get_product_by_id(product_id[0].discount_line_product_id[0]);
        product.display_name = product.name
        product.display_name = product.display_name + " Code: " +  order.voucher_code

        order.add_product(product, {
            quantity: 1,
            price:    amount_total,
            merge:    false,
            uom_id:   [1, 'Unidad'],
        });

        const product_voucher_id =  await this.env.services.orm.call(
            "loyalty.reward",
            "search_read",
            [
                [["program_id", "=", loyalty_program_id]],            // domain
                ["discount_line_product_id"]                          // fields
            ],
            { limit: 1, order: "id asc" }                           // kwargs opcional
        );
        order.product_voucher_id = product_voucher_id?.[0]?.discount_line_product_id?.[0] ?? null;
    },

    async fetch_reward(id){
        id = Number(id);
        const res = await this.orm.call("loyalty.reward","read",[[id],[
            "id","program_id","reward_type","discount_line_product_id",
            "reward_product_id","required_points","active","company_id"
        ]]);
        const r = res?.[0] || null;
        return r;
    },

    // clear_coupon(o) {
    //     if (!o) return;
    //     o.codeActivatedCoupons = [];
    //     o.codeActivatedProgramRules = [];
    //     o.couponPointChanges = [];
    //     order.disabledRewards.clear();
    //     o.get_orderlines()
    //     .filter(l => l.is_reward_line || l.reward_rule_id)
    //     .forEach(l => (o.remove_orderline || o.removeOrderline)?.(l));
    // },

    async onMounted() {
        this.getLocalCashTotal();
        
        await this.clear_pay_method();
        const { updated } =  this.orm.call(
            "loyalty.card",
            "sync_source_order_by_posref",
            [],                 // args
            { limit: 1000 }     // kwargs opcional
        );
        console.log("loyalty.cards actualizados:", updated);

        /******************* APLICAR PRECIO PROPORCIONAL CON DESCUENTO GLOBAL *******************/
        console.log("🔧 CALCULADOR PROPORCIONAL - Verificando líneas de cambios...");
        
        // Esperar un momento para que la orden esté completamente cargada
        setTimeout(() => {
            this.applyProportionalPriceToChangeLines();
        }, 1000);
    },

    async applyProportionalPriceToChangeLines() {
        try {
            console.log("🟢 APLICANDO PRECIO PROPORCIONAL MEJORADO (MEMORIA)");
            
            const order = this.pos.get_order();
            if (!order || !order.get_orderlines) return;

            // DEBUG COMPLETO
            console.log("=== 🎯 DEBUG PRODUCTSCREEN 🎯 ===");
            console.log("📋 Orden actual:", order.name);
            console.log("🔑 changes_codes:", order.changes_codes);
            console.log("💾 POS cache disponible:", !!this.pos.originalOrderDiscountInfo);
            if (this.pos.originalOrderDiscountInfo) {
                console.log("🗂️ Claves en cache:", Object.keys(this.pos.originalOrderDiscountInfo));
                console.log("📝 Contenido del cache:", this.pos.originalOrderDiscountInfo);
            }
            console.log("=================================");
            
            const allOrderLines = order.get_orderlines();
            console.log(`🔧 ${allOrderLines.length} líneas en la orden`);
            
            const changeLines = this.getChangeLines(order, allOrderLines);
            
            if (changeLines.length > 0) {
                console.log(`🔧 ${changeLines.length} líneas de cambios detectadas`);
                
                const originalOrderInfo = this.findOriginalOrderFromChanges(order);
                
                if (originalOrderInfo && originalOrderInfo.hasGlobalDiscount) {
                    const discountPercentage = originalOrderInfo.globalDiscountPercentage;
                    const discountFactor = originalOrderInfo.globalDiscountFactor;
                    
                    console.log(`🎯 ✅✅✅ APLICANDO DESCUENTO PROPORCIONAL DEL ${discountPercentage}% ✅✅✅`);
                    
                    let cambiosAplicados = 0;
                    
                    changeLines.forEach((changeLine, index) => {
                        const precioOriginal = Math.abs(this.getLineUnitPrice(changeLine));
                        const precioProporcional = precioOriginal * discountFactor;
                        const precioFinal = -Math.round(precioProporcional * 100) / 100;
                        
                        console.log(`🔧 Línea ${index + 1}: ${precioOriginal} → ${precioFinal}`);
                        
                        const success = this.setLineUnitPrice(changeLine, precioFinal);
                        
                        if (success) {
                            cambiosAplicados++;
                            console.log(`✅ PRECIO ACTUALIZADO: ${precioOriginal} → ${this.getLineUnitPrice(changeLine)}`);
                        }
                    });
                    
                    console.log(`🔧 RESUMEN: ${cambiosAplicados} líneas actualizadas con descuento del ${discountPercentage}%`);
                    
                    if (cambiosAplicados > 0) {
                        this.forceUIRefresh();
                    }
                } else {
                    console.log(`🔧 Orden original NO tiene descuento global, no se aplica ajuste proporcional`);
                }
            }
            
        } catch (error) {
            console.error("❌ ERROR:", error);
        }
    },

    /**
     * Encuentra la orden original basada en los cambios - VERSIÓN SIMPLIFICADA Y EFECTIVA
     */
    findOriginalOrderFromChanges(currentOrder) {
        try {
            console.log("🔧 Buscando información de descuento en cache del POS...");
            
            if (!currentOrder.changes_codes) {
                console.log("🔧 ❌ No hay changes_codes en la orden actual");
                return null;
            }
            
            console.log(`🔧 changes_codes actual: '${currentOrder.changes_codes}'`);
            
            // VERIFICAR SI EXISTE EL CACHE EN EL POS
            if (!this.pos.originalOrderDiscountInfo) {
                console.log("🔧 ❌ No hay cache de descuentos en el POS");
                return null;
            }
            
            console.log("🔧 Cache disponible en POS:", Object.keys(this.pos.originalOrderDiscountInfo));
            
            // BUSCAR COINCIDENCIA EXACTA EN EL CACHE
            const discountInfo = this.pos.originalOrderDiscountInfo[currentOrder.changes_codes];
            if (discountInfo) {
                console.log(`🔧 ✅ COINCIDENCIA EXACTA ENCONTRADA!`);
                console.log(`🔧 Orden original: ${discountInfo.originalOrderName}`);
                console.log(`🔧 Descuento: ${discountInfo.discountPercentage}%`);
                
                return {
                    hasGlobalDiscount: discountInfo.hasGlobalDiscount,
                    globalDiscountPercentage: discountInfo.discountPercentage,
                    globalDiscountFactor: discountInfo.discountFactor,
                    name: discountInfo.originalOrderName,
                    source: "exact_cache_match"
                };
            }
            
            // BUSCAR COINCIDENCIA PARCIAL (por si hay diferencias de formato)
            for (const [cacheKey, cacheInfo] of Object.entries(this.pos.originalOrderDiscountInfo)) {
                if (currentOrder.changes_codes.includes(cacheKey.trim()) || 
                    cacheKey.includes(currentOrder.changes_codes.trim())) {
                    
                    console.log(`🔧 ✅ COINCIDENCIA PARCIAL ENCONTRADA!`);
                    console.log(`🔧 Clave en cache: '${cacheKey}'`);
                    console.log(`🔧 Orden original: ${cacheInfo.originalOrderName}`);
                    console.log(`🔧 Descuento: ${cacheInfo.discountPercentage}%`);
                    
                    return {
                        hasGlobalDiscount: cacheInfo.hasGlobalDiscount,
                        globalDiscountPercentage: cacheInfo.discountPercentage,
                        globalDiscountFactor: cacheInfo.discountFactor,
                        name: cacheInfo.originalOrderName,
                        source: "partial_cache_match"
                    };
                }
            }
            
            console.log("🔧 ❌ No se encontró coincidencia en el cache");
            console.log("🔧 Búsquedas intentadas:");
            console.log("🔧 - Coincidencia exacta con:", currentOrder.changes_codes);
            console.log("🔧 - Coincidencia parcial con todas las claves del cache");
            
            return null;
            
        } catch (error) {
            console.error("🔧 ❌ Error buscando en cache:", error);
            return null;
        }
    },


    /**
     * Obtiene detalles completos de una orden - VERSIÓN CORREGIDA Y ROBUSTA
     */
    async getOrderDetails(orderId) {
        try {
            console.log(`🔧 getOrderDetails - Buscando orden ID: ${orderId}`);
            
            // PRIMERO: Obtener la orden básica con campos esenciales
            const orders = await this.orm.call("pos.order", "search_read", [
                [["id", "=", orderId]],
                ["id", "name", "pos_reference", "amount_total", "amount_tax", "amount_untaxed"]
            ]);

            console.log(`🔧 Resultado búsqueda orden:`, orders);

            if (!orders || orders.length === 0) {
                console.log(`🔧 ❌ Orden ${orderId} no encontrada`);
                return null;
            }

            const originalOrder = orders[0];
            console.log(`🔧 ✅ Orden básica encontrada:`, {
                id: originalOrder.id,
                name: originalOrder.name,
                total: originalOrder.amount_total
            });

            // SEGUNDO: Obtener las líneas de la orden con manejo de errores
            let originalLines = [];
            try {
                originalLines = await this.orm.call("pos.order.line", "search_read", [
                    [["order_id", "=", orderId]],
                    ["id", "price_unit", "qty", "discount", "product_id", "price_subtotal", "price_subtotal_incl", "name"]
                ]);
                console.log(`🔧 ✅ ${originalLines.length} líneas obtenidas`);
            } catch (lineError) {
                console.error("🔧 ❌ Error obteniendo líneas:", lineError);
                // Continuamos con líneas vacías en lugar de fallar completamente
            }

            // TERCERO: Log detallado de las líneas
            if (originalLines.length > 0) {
                console.log("🔧 Detalles de líneas:");
                originalLines.forEach((line, index) => {
                    console.log(`🔧 Línea ${index}: ${line.name || 'Sin nombre'} - Precio: ${line.price_unit}, Cant: ${line.qty}, Desc: ${line.discount}%`);
                });
            } else {
                console.log("🔧 ⚠️ No se obtuvieron líneas de la orden");
            }

            return {
                order: originalOrder,
                lines: originalLines
            };

        } catch (error) {
            console.error("🔧 ❌❌❌ ERROR CRÍTICO en getOrderDetails:", error);
            console.error("🔧 Stack trace:", error.stack);
            return null;
        }
    },

    /**
     * Obtiene el precio unitario de una línea de forma segura
     */
    getLineUnitPrice(line) {
        try {
            if (typeof line.get_unit_price === 'function') {
                return line.get_unit_price();
            }
            if (line.price !== undefined) {
                return line.price;
            }
            if (line.unit_price !== undefined) {
                return line.unit_price;
            }
            return 0;
        } catch (error) {
            console.error("🔧 Error obteniendo precio de línea:", error);
            return 0;
        }
    },

    /**
     * Establece el precio unitario de una línea de forma segura - MEJORADO
     */
    setLineUnitPrice(line, price) {
        try {
            console.log(`🔧 setLineUnitPrice: Intentando establecer precio ${price} en línea ${line.id}`);
            
            // Método 1: set_unit_price si existe
            if (typeof line.set_unit_price === 'function') {
                line.set_unit_price(price);
                console.log(`✅ Precio establecido via set_unit_price`);
                return true;
            }
            
            // Método 2: Asignación directa a price
            if (line.price !== undefined) {
                line.price = price;
                console.log(`✅ Precio establecido via line.price`);
                return true;
            }
            
            // Método 3: Asignación directa a unit_price
            if (line.unit_price !== undefined) {
                line.unit_price = price;
                console.log(`✅ Precio establecido via line.unit_price`);
                return true;
            }
            
            // Método 4: Usar set_price si existe
            if (typeof line.set_price === 'function') {
                line.set_price(price);
                console.log(`✅ Precio establecido via set_price`);
                return true;
            }
            
            console.log(`❌ No se pudo encontrar método para establecer precio`);
            return false;
            
        } catch (error) {
            console.error(`❌ Error en setLineUnitPrice:`, error);
            return false;
        }
    },

    /**
     * Identifica las líneas que representan cambios
     */
    getChangeLines(order, orderLines) {
        const changeLines = [];

        // Método 1: Líneas que son el producto especial de cambios
        if (order.product_changes_id) {
            const productChangeLines = orderLines.filter(line => 
                line.product && line.product.id === order.product_changes_id
            );
            changeLines.push(...productChangeLines);
            console.log(`🔧 ${productChangeLines.length} líneas con product_changes_id: ${order.product_changes_id}`);
        }

        // Método 2: Líneas con changes > 0
        const linesWithChanges = orderLines.filter(line => line.changes > 0);
        linesWithChanges.forEach(line => {
            if (!changeLines.includes(line)) {
                changeLines.push(line);
            }
        });
        console.log(`🔧 ${linesWithChanges.length} líneas con changes > 0`);

        // Método 3: Líneas que tienen changes_codes en su nombre
        const codes = order.changes_codes ? String(order.changes_codes) : "";

        if (codes.trim() !== "") {
            const linesWithChangeCodes = orderLines.filter(line =>
                // Usamos la variable segura 'codes' en lugar de order.changes_codes
                line.full_product_name && line.full_product_name.includes(codes)
            );
            linesWithChangeCodes.forEach(line => {
                if (!changeLines.includes(line)) {
                    changeLines.push(line);
                }
            });
            console.log(`🔧 ${linesWithChangeCodes.length} líneas con changes_codes`);
        }

        console.log(`🔧 Total de líneas de cambios identificadas: ${changeLines.length}`);
        return changeLines;
    },
    /**
     * Fuerza actualización de la UI
     */
    forceUIRefresh() {
        try {
            // Método 1: Intentar render del componente
            if (this.render && typeof this.render === 'function') {
                this.render();
            }
            
            // Método 2: Disparar evento de cambio en el pos
            if (this.pos && typeof this.pos.trigger === 'function') {
                this.pos.trigger('change');
            }
            
            // Método 3: Disparar evento global
            setTimeout(() => {
                window.dispatchEvent(new Event('resize'));
            }, 100);
            
        } catch (error) {
            console.error("🔧 Error forzando refresh UI:", error);
        }
    },

async clickReembolso(){
        const { confirmed, payload } = await this.popup.add(MaskedInputPopup,{
            title: "Devoluciones y Cancelaciones",
            body: "Ingresa el número de orden:",
            placeholder: "Ej: 00001",
            resolve: (result) => {
                console.log("Popup cerrado:", result);
            }
        });

        if (!confirmed || !payload) return;

        try {
            // Limpiar y formatear el número de orden
            const orderNumber = String(payload).trim();
            console.log("🔍 Buscando orden:", orderNumber);

            // ✅ PASO 1: Pedir el motivo ANTES de buscar la orden
            console.log("📝 Solicitando motivo de la operación...");
            const refundReason = await this.getRefundReason();

            if (!refundReason || refundReason.trim() === '') {
                await this.popup.add(ErrorPopup, {
                    title: "Motivo requerido",
                    body: "Debes especificar el motivo para continuar con la operación.",
                });
                return;
            }

            console.log("✅ Motivo capturado:", refundReason);
            // Guardar el motivo temporalmente
            this.pos.currentRefundReason = refundReason;

            // Buscar la orden ORIGINAL usando varios métodos
            let originalOrder = null;

            // Método 1: Buscar por nombre exacto
            const ordersByName = await this.orm.call("pos.order", "search_read", [
                [["name", "=", orderNumber]],
                ["id", "pos_reference", "partner_id", "fiscal_position_id", "name", "changes_codes", "state", "amount_total"]
            ], { limit: 1 });

            if (ordersByName && ordersByName.length > 0) {
                originalOrder = ordersByName[0];
            } else {
                // Método 2: Buscar por pos_reference
                const ordersByRef = await this.orm.call("pos.order", "search_read", [
                    [["pos_reference", "ilike", orderNumber]],
                    ["id", "pos_reference", "partner_id", "fiscal_position_id", "name", "changes_codes", "state", "amount_total"]
                ], { limit: 1 });

                if (ordersByRef && ordersByRef.length > 0) {
                    originalOrder = ordersByRef[0];
                } else {
                    // Método 3: Buscar por ID numérico
                    const orderId = parseInt(orderNumber);
                    if (!isNaN(orderId)) {
                        const ordersById = await this.orm.call("pos.order", "search_read", [
                            [["id", "=", orderId]],
                            ["id", "pos_reference", "partner_id", "fiscal_position_id", "name", "changes_codes", "state", "amount_total"]
                        ], { limit: 1 });

                        if (ordersById && ordersById.length > 0) {
                            originalOrder = ordersById[0];
                        }
                    }
                }
            }

            if (!originalOrder) {
                await this.popup.add(ErrorPopup, {
                    title: "Orden no encontrada",
                    body: `No se encontró la orden "${orderNumber}". Verifica el número e intenta nuevamente.`,
                });
                delete this.pos.currentRefundReason;
                return;
            }

            // Verificar estado válido
            const validStates = ["paid", "done", "invoiced"];
            if (!validStates.includes(originalOrder.state)) {
                await this.popup.add(ErrorPopup, {
                    title: "Orden no válida",
                    body: `La orden ${originalOrder.name} está en estado "${originalOrder.state}". Solo se pueden reembolsar órdenes pagadas.`,
                });
                delete this.pos.currentRefundReason;
                return;
            }

            // Validar cambios existentes
            const hasExistingChanges = originalOrder.changes_codes &&
                                    originalOrder.changes_codes.trim() !== "" &&
                                    originalOrder.changes_codes !== " ";

            if (hasExistingChanges) {
                await this.popup.add(ErrorPopup, {
                    title: "Cambios no permitidos",
                    body: "Esta orden ya tiene cambios realizados. No se pueden realizar reembolsos sobre órdenes con cambios previos.",
                });
                delete this.pos.currentRefundReason;
                return;
            }

            // Validar si es un reembolso
            const orderName = originalOrder.name || "";
            const posReference = originalOrder.pos_reference || "";

            if (orderName.includes("REEMBOLSO") ||
                orderName.includes("DEVOLUCIÓN") ||
                orderName.includes("REFUND") ||
                posReference.includes("REEMBOLSO") ||
                posReference.includes("DEV") ||
                posReference.includes("REFUND")) {

                await this.popup.add(ErrorPopup, {
                    title: "Operación no válida",
                    body: "No se puede reembolsar una orden que ya es un reembolso.",
                });
                delete this.pos.currentRefundReason;
                return;
            }

            // Validar caché local
            const refundKey = `refund_${originalOrder.id}`;
            const existingRefund = localStorage.getItem(refundKey);

            if (existingRefund) {
                const refundDate = new Date(parseInt(existingRefund));
                await this.popup.add(ErrorPopup, {
                    title: "Reembolso ya realizado",
                    body: `Esta orden ya fue reembolsada localmente el ${refundDate.toLocaleString()}.`,
                });
                delete this.pos.currentRefundReason;
                return;
            }

            // ✅ AQUÍ ESTÁ EL CAMBIO CLAVE: ConfirmPopup SIN HTML ✅
            // Usamos template literals (``) y \n para los saltos de línea.
            const { confirmed: finalConfirm } = await this.popup.add(ConfirmPopup, {
                title: _t("Confirmar Devolución"),
                body: `Orden: ${originalOrder.name}
                Total: $${Math.abs(originalOrder.amount_total).toFixed(2)}

                Motivo: ${refundReason}

                ¿Estás seguro de continuar con la devolución?`,
                confirmText: _t("Sí, devolver"),
                cancelText: _t("Cancelar")
            });

            if (!finalConfirm) {
                delete this.pos.currentRefundReason;
                return;
            }

            // Buscar líneas de la orden
            console.log("🔍 Buscando líneas de la orden ID:", originalOrder.id);
            const orderLines = await this.orm.call("pos.order.line", "search_read", [
                [["order_id", "=", originalOrder.id]],
                [
                    "id", "product_id", "qty", "price_unit", "discount", "price_subtotal",
                    "tax_ids", "combo_parent_id", "combo_line_ids", "full_product_name"
                ]
            ]);

            console.log("Líneas encontradas:", orderLines);

            if (!orderLines || orderLines.length === 0) {
                await this.popup.add(ErrorPopup, {
                    title: "Sin líneas para reembolsar",
                    body: "La orden no tiene líneas disponibles para reembolso.",
                });
                localStorage.removeItem(refundKey);
                delete this.pos.currentRefundReason;
                return;
            }

            // MARCAR INMEDIATAMENTE para prevenir doble reembolso
            localStorage.setItem(refundKey, Date.now().toString());

            // Cargar líneas en toRefundLines
            this.pos.toRefundLines = {};
            for (const line of orderLines) {
                this.pos.toRefundLines[line.id] = {
                    qty: line.qty,
                    orderline: line,
                    destinationOrderUid: null,
                };
            }

            // Obtener partner
            const partner = originalOrder.partner_id && originalOrder.partner_id[0]
                ? this.pos.db.get_partner_by_id(originalOrder.partner_id[0])
                : null;

            console.log("Partner para reembolso:", partner);

            // Obtener detalles reembolsables usando la lógica original
            const refundableDetails = _super_getRefundableDetails.call(this, partner); 

            if (!refundableDetails || refundableDetails.length === 0) {
                await this.popup.add(ErrorPopup, {
                    title: "Nada que reembolsar",
                    body: "No se encontraron líneas válidas para reembolso.",
                });
                localStorage.removeItem(refundKey);
                delete this.pos.currentRefundReason;
                return;
            }

            console.log("Detalles reembolsables:", refundableDetails);

            // Crear orden de destino
            const refundOrder = this.pos.get_order();
            refundOrder.is_return = true;
            
            // ✅ GUARDAR EL MOTIVO EN LA NUEVA ORDEN
            refundOrder.refund_cancel_reason = refundReason;

            if (partner) {
                refundOrder.set_partner(partner);
            }

            const originalToRefundLineMap = new Map();

            // ✅ Agregar productos a la orden de reembolso
            for (const detail of refundableDetails) {
                try {
                    const product = this.pos.db.get_product_by_id(detail.orderline.product_id[0]);
                    const options = _super_prepareRefundOrderlineOptions(detail);

                    // ✅ FORZAR pack_lot_lines a array vacío SIEMPRE
                    if (options) {
                        options.pack_lot_lines = [];
                    } else {
                        options = { pack_lot_lines: [] };
                    }

                    const refundLine = await refundOrder.add_product(product, options);
                    originalToRefundLineMap.set(detail.orderline.id, refundLine);
                    detail.destinationOrderUid = refundOrder.uid;
                    
                    console.log("✅ Producto agregado a reembolso:", product.display_name);
                } catch (error) {
                    console.error("❌ Error agregando producto:", error, detail);
                }
            }

            // Manejo de combos
            for (const detail of refundableDetails) {
                const originalLine = detail.orderline;
                const refundLine = originalToRefundLineMap.get(originalLine.id);

                if (originalLine.combo_parent_id && originalLine.combo_parent_id[0]) {
                    const parentLine = originalToRefundLineMap.get(originalLine.combo_parent_id[0]);
                    if (parentLine) refundLine.comboParent = parentLine;
                }

                if (originalLine.combo_line_ids?.length) {
                    refundLine.comboLines = originalLine.combo_line_ids
                        .map(id => originalToRefundLineMap.get(id))
                        .filter(Boolean);
                }
            }

            // Buscar pagos de la orden original
            const payments = await this.orm.call("pos.payment", "search_read", [
                [["pos_order_id", "=", originalOrder.id]],
                ["amount", "payment_method_id", "payment_date"]
            ]);

            console.log("Pagos encontrados:", payments);

            // Agregar pagos negativos a la orden de reembolso
            for (const payment of payments) {
                const method = this.pos.payment_methods.find(pm => pm.id === payment.payment_method_id[0]);
                if (method) {
                    const paymentLine = refundOrder.add_paymentline(method);
                    paymentLine.set_amount(payment.amount * -1); // Negativo para reembolso
                    console.log("✅ Pago agregado:", payment.amount * -1, method.name);
                }
            }

            // ✅ MARCAR LA ORDEN ORIGINAL COMO REEMBOLSADA EN EL SISTEMA CON EL MOTIVO
            try {
                await this.orm.call("pos.order", "write", [[originalOrder.id], {
                    refund_cancel_reason: refundReason,  // ✅ Guardar el motivo
                    note: `REEMBOLSADO - ${new Date().toLocaleString()} - Motivo: ${refundReason}`
                }]);
                console.log("✅ Orden original marcada como reembolsada con motivo:", refundReason);
            } catch (error) {
                console.log("⚠️ No se pudo marcar la orden en BD:", error);
            }

            // Redirigir a pantalla de pago
            this.pos.Sale_type = "Reembolso";
            this.pos.set_order(refundOrder);
            this.pos.Reembolso = true;
            
            console.log("✅ Reembolso creado, redirigiendo a pantalla de pago...");
            this.pos.showScreen("PaymentScreen");

            // ✅ Limpiar variables temporales
            delete this.pos.currentRefundReason;
            
            // ✅ Limpiar el localStorage después de 2 horas
            setTimeout(() => {
                localStorage.removeItem(refundKey);
                console.log("🗑️ Limpiada marca temporal de reembolso");
            }, 2 * 60 * 60 * 1000);

        } catch (error) {
            console.error("❌ ERROR CRÍTICO en clickReembolso:", error);
            // Limpiar variables temporales en caso de error
            delete this.pos.currentRefundReason;
            
            await this.popup.add(ErrorPopup, {
                title: "Error en reembolso",
                body: `Ocurrió un error inesperado: ${error.message || error}`,
            });
        }
    },

    async clear_pay_method(){
        const order = this.pos.get_order?.();
        if (order) {
            const lines = order.get_paymentlines?.() || [];
            for (const l of [...lines]) {
                (order.remove_paymentline || order.removePaymentline || order.removePaymentLine)?.call(order, l);
            }
        }
    },


    async Discount(amount, rate) {
        //Aplica descuento del 10%
        rate = rate / 100
        const cents = Math.round(amount * 100);
        const discounted = Math.round(cents * (1 - rate));
        return discounted / 100; // regresa en unidades, ej. 89.99
    },


    async get_cash_out() {
        const sessionId = this.pos?.pos_session?.id;
        // 1) Leer líneas de extracto de caja de la sesión
        const lines = await this.orm.call(
            "account.bank.statement.line",
            "search_read",
            [[["pos_session_id", "=", sessionId]]],
            { fields: ["amount", "payment_ref", "date", "statement_id", "journal_id"] }
        );

        let totalIn = 0, totalOut = 0;
        for (const l of lines) {
            const amt = Number(l.amount) || 0;
            if (amt >= 0) totalIn += amt;
            else totalOut += Math.abs(amt);
        }

        totalIn  = Math.round(totalIn  * 100) / 100;
        totalOut = Math.round(totalOut * 100) / 100;
        const net = Math.max(0, Math.round((totalIn - totalOut) * 100) / 100);
        //console.log("Cash In:", totalIn, "Cash Out:", totalOut, "Neto:", net);
        return totalOut
    },


    async sum_cash(){
        const sessionId = this.posService.pos_session.id;
        const cashMethodIds = (this.posService.payment_methods || [])
            .filter(pm => pm.type === "cash" || pm.is_cash_count) // ambas opciones por compatibilidad
            .map(pm => pm.id);

        if (!cashMethodIds.length) {
            this.cashTotal.value = 0;
            return;
        }

        const domain = [
            ["session_id", "=", sessionId],
            ["payment_method_id", "in", cashMethodIds],
        ];

        const total_sale = await this.orm.call(
            "pos.payment",
            "read_group",
            [domain, ["amount:sum"], []],
            {}
        );

        let total = 0;
        if (total_sale && total_sale.length) {
            total = Number(total_sale[0].amount || 0);
        } // else {
        //     // 2) Fallback: sumar con search_read
        //     const recs = await this.orm.searchRead("pos.payment", domain, ["amount"]);
        //     total = (recs || []).reduce((acc, r) => acc + Number(r.amount || 0), 0);
        // }
        return total
    },

    async getLocalCashTotal() {
        this.cashTotal = await this.sum_cash();
        const cfgId = this.pos?.config?.id || false;
        const withdrawal = await this.orm.call("pos.config", "get_withdrawal", [cfgId], {});
        const cash_out = await this.get_cash_out();

        //Aqui le descento el 10% 
        let discounted = await this.Discount(withdrawal,10)

        if (this.cashTotal - cash_out >= discounted) {
            await this.popup.add(ErrorPopup, {
                title: "Aviso de retiro",
                body: "Solicitar un retiro de efectivo",
                confirmText: "OK",
            });

            //cambio de color el boton de pago.
            const button = document.querySelector("button.pay-order-button");
            if (button) {
                button.classList.add("btn-highlighted");
            }
        }
        if (this.cashTotal - cash_out > withdrawal){
            this.pos.bloqueodecaja = true
        }
        else{
            this.pos.bloqueodecaja = false
        }
    },

    get productsToDisplay() {
        const original = this._super?.(...arguments) || [];

        let list = original;
        if (typeof list?.[0] === "number") {
            const { db } = this.pos;
            list = list.map((id) => db.get_product_by_id(id));
        }

        //  Decorar nombres (conservar orden original; no volver a ordenar)
        return list.map(decorateName);
    },

    async onNumpadClick(mode) {
        if (mode === "price" || mode === "discount" ) {
            await this.change_price_desc(mode);
        }
        return _superSetNumpadMode.call(this, mode);
    },

    getTotalItems() {
        const order = this.pos.get_order();
        if (!order) return 0;
        return order.orderlines.reduce((sum, line) => sum + line.quantity, 0);
    },

    async clickVale(){
        const order = this.pos.get_order?.();
        const amount_total = order?.get_total_with_tax?.() ?? 0;
        await this.createvale_screen(amount_total)
    },

    async change_price_desc(mode) {
        const { popup, orm } = this.env.services;

        const { confirmed, payload } = await  this.popup.add(PasswordInputPopup, {
            title: _t("Contraseña de supervisor"),
            body: _t("Ingresa el NIP del Gerente de Ventas:"),
            confirmText: _t("Validar"),
            cancelText: _t("Cancelar"),
        });

        if (!confirmed || !payload) {
            return; 
        }

        const nip = String(payload).trim();
        if (!nip) return;
    
        let check = { ok: false, name: "" };
        try {
            check = await orm.call("hr.employee", "check_pos_nip", [nip], {});
            const advancedEmployeeIds = this.pos.config.advanced_employee_ids; // Lista de IDs
            const isAdvancedUser = advancedEmployeeIds.includes(check.id);
            if (!isAdvancedUser){
                this.popup.add(ErrorPopup, {
                    title: _t("Validacion supervisor"),
                    body:  _t("No es usuario supervisor"),
                });
                return;
            }

            if (isAdvancedUser && mode === "price")  {
                this.change_price()
            } 

            if (check.ok && mode === "discount")  {
                const order = this.posService.get_order();
                const partner = order?.get_partner?.() || order?.get_client?.() || null;
                let Is_employee = null
                const orderlines = order.get_orderlines()
                const match = 'descuento';

                const discountLines = orderlines.filter(line => {
                // intentar obtener el nombre del producto de formas comunes
                const prodName =
                (line.product && line.product.name) ||
                line.product_name ||
                line.name ||
                line.display_name ||
                '';

                return typeof prodName === 'string' && prodName.toLowerCase().includes(match.toLowerCase());
                });

                if (discountLines.length > 0){
                    this.popup.add(ErrorPopup, {
                        title: _t("Descuentos"),
                        body:  _t("Ya exite un desuento global"),
                    });
                    return;
                }

                if (partner) {
                    console.log("Is_employee",Is_employee)
                    Is_employee = await this.orm.call(
                        "hr.employee","search_read",
                        [[["work_contact_id","=",partner.id]],
                        ["id","name"]
                        ],
                        {limit:1}
                    );
                }
                
                if (Is_employee?.length){
                    const discountLines = orderlines.filter(line => line.discount > 0);
                    if (discountLines.length > 0){
                        this.popup.add(ErrorPopup, {
                            title: _t("Descuentos"),
                            body:  _t("Ya exite un desuento en la venta"),
                        });
                        return;
                    }

                    const cfgId = this.pos?.config?.id || false;
                    const employee_discount = await this.orm.call("pos.config", "get_employee_discount", [cfgId], {});

                    await this.popup.add(ConfirmPopup, {
                        title: "Confirmación de descuento",
                        body: "¿Desea aplicar descuento al empleado?",
                    }).then(({ confirmed }) => {
                    if (confirmed) {
                        console.log("confimado")
                            this.env.bus.trigger("trigger-discount", { pc: 10 });
                        }
                    });
                }
                else {
                    this.change_desc()
                }

            } 

        } catch (err) {
            console.error("Error al validar NIP:", err);
                await popup.add(TextInputPopup, {
                title: "Error",
                body: "No se pudo validar el NIP. Revisa el servidor.",
                confirmText: "OK",
            });
            return;
        }
        return;
    },

    async change_price() {
        const order = this.pos.get_order();
        const line  = order?.get_selected_orderline();
        if (!line) {
            this.popup.add(ErrorPopup, {
                title: _t("Sin línea seleccionada"),
                body:  _t("Selecciona una línea del ticket para cambiar el precio."),
            });
            return;
        }
        //const current = line.get_unit_price();
        const { confirmed, payload } = await this.popup.add(TextInputPopup, {
            title: _t("Nuevo precio unitario"),
            body:  _t("Ingresa el precio."),
            inputProps: { type: "number", inputmode: "decimal", pattern: "[0-9]*[.]?[0-9]*", className: "verde-input", },
            confirmText: _t("Aplicar"),
            cancelText: _t("Cancelar"),
        });

        if (!confirmed) return;
            const value = parseFloat(payload);
            if (!isFinite(value) || value <= 0) {
                this.popup.add(ErrorPopup, {
                    title: _t("Precio inválido"),
                    body:  _t("Ingresa un número mayor que 0."),
                });
                return;
            }
        // aqui retorno el precio
        line.set_unit_price(value/1.16);
    },

    async change_desc() {
        const order = this.pos.get_order();
        const line  = order?.get_selected_orderline();

        if (!line) {
            this.popup.add(ErrorPopup, {
                title: _t("Sin línea seleccionada"),
                body:  _t("Selecciona una línea del ticket para aplicar descuento."),
            });
            return;
        }

        const current = line.get_discount();
        const { confirmed, payload } = await this.popup.add(TextInputPopup, {
            title: _t("Nuevo descuento"),
            body:  _t("Ingresa el descuento en porcentaje (ej. 10 para 10%)."),
            startingValue: "", //String(current),
            inputProps: { type: "number", inputmode: "decimal", pattern: "[0-9]*[.]?[0-9]*",className: "verde-input", },
            confirmText: _t("Aplicar"),
            cancelText: _t("Cancelar"),
        });

        if (!confirmed) return;

        const value = parseFloat(payload);
        if (!isFinite(value) || value < 0 || value > 100) {
            this.popup.add(ErrorPopup, {
                title: _t("Descuento inválido"),
                body:  _t("Ingresa un número entre 0 y 100."),
            });
            return;
        }
        line.set_discount(value);
    },

    async openCashDrawer() {
        try {
            // 1. Pedir contraseña del operador
            const { confirmed, payload } = await this.popup.add(PasswordInputPopup, {
                title: _t("Apertura de Cajón"),
                body: _t("Ingresa tu contraseña para abrir el cajón:"),
                confirmText: _t("Abrir"),
                cancelText: _t("Cancelar"),
            });

            if (!confirmed || !payload) {
                return; // Usuario canceló
            }

            // 2. Validar contraseña del operador actual
            const password = String(payload).trim();
            let employeeCheck = { ok: false, name: "", id: null };
            
            try {
                employeeCheck = await this.orm.call("hr.employee", "check_pos_nip", [password], {});
            } catch (err) {
                console.error("Error al validar contraseña:", err);
                await this.popup.add(ErrorPopup, {
                    title: "Error de validación",
                    body: "No se pudo validar la contraseña. Intenta nuevamente.",
                });
                return;
            }

            if (!employeeCheck.ok) {
                await this.popup.add(ErrorPopup, {
                    title: "Contraseña incorrecta",
                    body: "La contraseña ingresada no es válida.",
                });
                return;
            }

            console.log("🔑 Contraseña válida. Operador:", employeeCheck.name);
            
            // 3. Intentar abrir el cajón
            console.log("🔵 Intentando abrir cajón...");

            let cajonAbierto = false;
            let metodoUsado = "";

            // Camino 1: hardwareProxy.openCashbox
            if (this.pos.hardwareProxy && typeof this.pos.hardwareProxy.openCashbox === 'function') {
                console.log("🔵 Camino 1: Usando hardwareProxy.openCashbox()");
                const success = await this.pos.hardwareProxy.openCashbox();
                console.log("✅ hardwareProxy.openCashbox() ejecutado, resultado:", success);
                
                if (success) {
                    cajonAbierto = true;
                    metodoUsado = "hardwareProxy.openCashbox";
                    console.log("🟢 ÉXITO - Cajón abierto via hardwareProxy.openCashbox()");
                } else {
                    console.log("🟡 hardwareProxy.openCashbox() devolvió false, probando siguiente método...");
                }
            }

            // Camino 2: Comando ESC/POS si el primero falló
            if (!cajonAbierto && this.pos.hardwareProxy && this.pos.hardwareProxy.printer) {
                console.log("🔵 Camino 2: Usando hardwareProxy.printer con comando ESC/POS");
                try {
                    const command = "\x1B\x70\x00\x19\xFA"; // Comando estándar para abrir cajón
                    console.log("📋 Enviando comando ESC/POS");
                    await this.pos.hardwareProxy.printer.printReceipt(command);
                    cajonAbierto = true;
                    metodoUsado = "ESC/POS command";
                    console.log("🟢 ÉXITO - Cajón abierto via comando ESC/POS");
                } catch (error) {
                    console.error("❌ Error con comando ESC/POS:", error);
                }
            }

            if (!cajonAbierto) {
                console.log("❌ TODOS los caminos fallaron");
                throw new Error("No se pudo acceder al dispositivo del cajón");
            }

            // 4. Registrar la apertura en el servidor
            try {
                const ahora = new Date().toISOString();
                console.log("📝 Registrando apertura de cajón...");
                
                // Guardar en el servidor
                await this.orm.call(
                    "pos.session", 
                    "register_cash_drawer_open", 
                    [this.pos.pos_session.id, employeeCheck.id, ahora, metodoUsado], 
                    {}
                );
                
                console.log("✅ Registro guardado en servidor");
                
            } catch (error) {
                console.error("⚠️ No se pudo guardar el registro en servidor:", error);
                // Fallback: guardar en localStorage
                try {
                    const registro = {
                        empleado_id: employeeCheck.id,
                        empleado_nombre: employeeCheck.name,
                        fecha_hora: new Date().toISOString(),
                        metodo: metodoUsado,
                        session_id: this.pos.pos_session.id
                    };
                    
                    const registrosExistentes = JSON.parse(localStorage.getItem('cash_drawer_open_logs') || '[]');
                    registrosExistentes.push(registro);
                    localStorage.setItem('cash_drawer_open_logs', JSON.stringify(registrosExistentes));
                    
                    console.log("📋 Registro guardado en localStorage");
                } catch (localError) {
                    console.error("❌ No se pudo guardar ni en localStorage:", localError);
                }
            }

            // 5. Mostrar mensaje de éxito
            this.notification.add(`Cajón abierto por ${employeeCheck.name} ✓`, { type: "success" });
            console.log("🎉 Apertura de cajón completada exitosamente");

        } catch (error) {
            console.error("🔴 ERROR en openCashDrawer:", error);
            // Solo log en consola, sin mostrar popup de error al usuario
        }
    },

    async getRefundReason() {
        try {
            // 1. Definir las opciones para el SelectionPopup
            // 'label' es lo que ve el usuario, 'item' es el valor que recibimos al seleccionar
            const selectionList = [
                { id: 1, label: _t("Producto defectuoso"), item: "Producto defectuoso" },
                { id: 2, label: _t("Cliente arrepentido"), item: "Cliente arrepentido" },
                { id: 3, label: _t("Error en el pedido"), item: "Error en el pedido" },
                { id: 4, label: _t("Producto incorrecto"), item: "Producto incorrecto" },
                { id: 5, label: _t("Cambio de talla/color"), item: "Cambio de talla/color" },
                { id: 6, label: _t("Problemas de entrega"), item: "Problemas de entrega" },
                { id: 7, label: _t("Cancelación por cliente"), item: "Cancelación por cliente" },
                { id: 8, label: _t("Error en precio"), item: "Error en precio" },
                { id: 9, label: _t("Producto agotado"), item: "Producto agotado" },
                { id: 10, label: _t("Otro motivo / Personalizado"), item: "custom_reason_flag" } // Usamos una bandera especial
            ];

            // 2. Mostrar el popup de selección (Clicable)
            const { confirmed, payload: selectedItem } = await this.popup.add(SelectionPopup, {
                title: _t("Seleccionar Motivo de Devolución"),
                list: selectionList,
            });

            if (!confirmed) return null;

            // 3. Procesar la selección
            
            // Si eligió la opción personalizada ("custom_reason_flag")
            if (selectedItem === "custom_reason_flag") {
                const { confirmed: inputConfirmed, payload: customReason } = await this.popup.add(TextInputPopup, {
                    title: _t("Motivo Personalizado"),
                    body: _t("Por favor, describe el motivo de la devolución:"),
                    placeholder: _t("Ej: El cliente cambió de opinión..."),
                    inputProps: {
                        multiline: true, // Esto no siempre funciona en POS nativo, pero es intentable
                    },
                    confirmText: _t("Guardar"),
                    cancelText: _t("Cancelar")
                });

                if (!inputConfirmed || !customReason.trim()) return null;
                return customReason.trim();
            }

            // Si eligió una opción de la lista estándar, devolvemos el texto directamente
            return selectedItem;

        } catch (error) {
            console.error("Error en getRefundReason:", error);
            return null;
        }
    },
});