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
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";

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
        if (this.pos.couponPointChanges) this.pos.couponPointChanges = [];
        //this.pos.sum_cash =  async () => {return await this.sum_cash();};
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
                    </div>`),
            });
        });
        
        // **************   para hacer pruebad en productscreen  *******************
        useHotkey("alt+x", (ev) => {                        
            //this.createvale()
            
             const order = this.pos.get_order();
             console.log("order",order);
            // const { updated } =  this.orm.call(
            //     "loyalty.card",
            //     "sync_source_order_by_posref",
            //     [],                 // args
            //     { limit: 1000 }     // kwargs opcional
            // );

            // console.log("loyalty.cards actualizados:", updated);
            console.log(this.pos.pos_session.user_id)
            console.log(this.pos.get_cashier()?.id )
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

    },

    async _getProductByBarcode(code) {
        // 🔁 Ejecutar la lógica original
        const product = await super._getProductByBarcode(code);

        // 🧩 Tu lógica adicional después de obtener el producto
        if (product && product.default_code) {
            product.display_name = `[${product.default_code}] ${product.display_name}`;
        }
        console.log("product",product);
        return product;
    },

    async createvale_screen(amount_total){
        if (amount_total > 0) {
            await this.popup.add(ErrorPopup, {
                title: "Error",
                body: "Para crear un vale el Total debe ser un valor negativo",
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
        product.display_name = product.display_name + " Code: " +  defaults.code
        
        order.add_product(product, {
            quantity: 1,
            price:    amount_total,
            merge:    false,
            uom_id:   [1, 'Unidad'],
        });

        // if (!this.currentOrder.couponPointChanges || Array.isArray(this.currentOrder.couponPointChanges)) {
        //     this.currentOrder.couponPointChanges = {};
        // }

        //const r = await this.fetch_reward(2);
        //console.log("r",r)
        //const l = order.add_product(this.pos.db.get_product_by_id(r.discount_line_product_id), { price: 0 });
        //console.log("l",l)
        

        // const changes = this.currentOrder.couponPointChanges;
        // let entry =
        // Object.values(changes).find(v => Number(v?.program_id) === Number(loyalty_program_id));

        // if (!entry) {
        // entry = {
        //     points: 1.0,// amount_total,
        //     barcode: defaults.code,
        //     //code: defaults.code,
        //     program_id: loyalty_program_id,
        //     coupon_id: -2,
        //     reward_id: 2,
        //     appliedRules: [2], //[loyalty_program_id],
        //    // expiration_date: new Date() + 30,   // ajusta si necesitas
        // };

        // const key = String(loyalty_program_id);
        // changes[key] = entry;
        // }
        
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
        console.log("r",r)
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
    },

    async clickReembolso(){
        const { confirmed, payload } = await this.popup.add(TextInputPopup, {
            title: _t("Reembolso por Ticket"),
            body: _t("Ingresa el número de ticket (pos_reference)."),
            placeholder: "S0001-001-0001",
            confirmText: _t("Buscar"),
            cancelText: _t("Cancelar"),
           inputProps: {
        onInput: (e) => {
                let input = e.target;
                let raw = input.value.replace(/[^0-9]/g, "").slice(0, 12); // Solo números
                let formatted = "S";

                if (raw.length > 0) formatted += raw.slice(0, 4);
                if (raw.length >= 5) formatted += "-" + raw.slice(4, 7);
                if (raw.length >= 8) formatted += "-" + raw.slice(7, 11);

                // Evita sobrescribir si el usuario borra
                input.value = formatted;

                // Reposiciona el cursor al final
                input.setSelectionRange(formatted.length, formatted.length);
            },
            maxlength: 17,
        },

        });
        console.log("confirmed",confirmed, "payload",payload);
       // const { confirmed, payload } = await this.showPopup(OrderNumberPopup);
        if (!confirmed || !payload) return;

        // Buscar la orden original
        const orderNumber = "Orden " + payload;
        const order = await this.orm.call("pos.order", "search_read", [
            [["pos_reference", "=", orderNumber]],
            ["id", "pos_reference", "partner_id", "fiscal_position_id"]
        ], { limit: 1 });
        

        if (!order || order.length === 0) {
            console.log("order",order);
            this.popup.add(ErrorPopup, {
            title: "Orden no encontrada",
            body: `No se encontró la orden ${orderNumber}`,
            });
            return;
        }

        // Buscar líneas de la orden
        const orderLines = await this.orm.call("pos.order.line", "search_read", [
            [["order_id", "=", order[0].id]],
            [
            "id", "product_id", "qty", "price_unit", "discount",
            "tax_ids", "combo_parent_id", "combo_line_ids"
            ]
        ]);

        for (const line of orderLines) {
            if (typeof line.pack_lot_lines === 'undefined') {
                line.pack_lot_lines = 0; // o [] si esperas una lista
            }
        }       
        
        if (!orderLines.length) {
            this.popup.add(ErrorPopup, {
            title: "Sin líneas para reembolsar",
            body: "La orden no tiene líneas disponibles para reembolso.",
            });
            return;
        }

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
        const partner = order.partner_id?.[0]
            ? this.pos.db.get_partner_by_id(order.partner_id[0])
            : null;

        // Obtener detalles reembolsables usando la lógica original
        const refundableDetails = _super_getRefundableDetails.call(this, partner); 

        if (!refundableDetails.length) {
            this.popup.add(ErrorPopup, {
            title: "Nada que reembolsar",
            body: "No se encontraron líneas válidas para reembolso.",
            });
            return;
        }

        // orden de destino
        const refundOrder = this.pos.get_order()
        refundOrder.is_return = true;

        if (partner) refundOrder.set_partner(partner);
        //if (order.fiscal_position) refundOrder.fiscal_position = order.fiscal_position;

        const originalToRefundLineMap = new Map();

        // Agregar productos con opciones completas
        for (const detail of refundableDetails) {
            const product = this.pos.db.get_product_by_id(detail.orderline.product_id[0]);
            const options = _super_prepareRefundOrderlineOptions(detail);
            const refundLine = await refundOrder.add_product(product, options);
            originalToRefundLineMap.set(detail.orderline.id, refundLine);
            detail.destinationOrderUid = refundOrder.uid;
        }

         // Manejo de combos
        for (const detail of refundableDetails) {
            const originalLine = detail.orderline;
            const refundLine = originalToRefundLineMap.get(originalLine.id);

            if (originalLine.combo_parent_id) {
            const parentLine = originalToRefundLineMap.get(originalLine.combo_parent_id[0]);
            if (parentLine) refundLine.comboParent = parentLine;
            }

            if (originalLine.combo_line_ids?.length) {
            refundLine.comboLines = originalLine.combo_line_ids.map(id => originalToRefundLineMap.get(id)).filter(Boolean);
            }
        }

        // Buscar pagos de la orden
        const payments = await this.orm.call("pos.payment", "search_read", [
            [["pos_order_id", "=", order[0].id]],
            ["amount", "payment_method_id"]
        ]);

        // Agregar pagos
        for (const payment of payments) {
            const method = this.pos.payment_methods.find(pm => pm.id === payment.payment_method_id[0]);
            if (method) {
                const paymentLine = refundOrder.add_paymentline(method);
                paymentLine.set_amount(payment.amount*-1);
            }
        }

        console.log("OrdenActual", this.pos.get_order())
        // Redirigir a pantalla de recibo
        this.pos.set_order(refundOrder);
        this.pos.Reembolso = true;
        this.pos.showScreen("PaymentScreen");
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
            title: _t("NIP"),
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
            console.log("nip",nip)
            check = await orm.call("hr.employee", "check_pos_nip", [nip], {});
            console.log("check",check)
            if (check.ok && mode === "price")  {
                this.change_price()
            } 

            if (check.ok && mode === "discount")  {
                this.change_desc()
            } 

        } catch (err) {
            console.error("Error al validar NIP:", err);
                await popup.add(TextInputPopup, {
                title: "Error",
                body: "No se pudo validar el NIP. Revisa el servidor.",
                startingValue: "",
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
            body:  _t("Ingresa el precio (usa punto decimal)."),
            //startingValue: String(current*1.16),
            // valida solo números con punto decimal (opcional)
            inputProps: { type: "text", inputmode: "decimal", pattern: "[0-9]*[.]?[0-9]*" },
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
            startingValue: String(current),
            inputProps: { type: "text", inputmode: "decimal", pattern: "[0-9]*[.]?[0-9]*" },
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
    }
});
