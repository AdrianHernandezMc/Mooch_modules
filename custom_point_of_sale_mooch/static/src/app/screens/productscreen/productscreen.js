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
                    </div>`),
            });
        });

        // **************   para hacer pruebad en productscreen  *******************
        useHotkey("alt+x", (ev) => {
            //this.createvale()
            const order = this.posService.get_order();
            const partner = order?.get_partner?.() || order?.get_client?.() || null;
            console.log("partner",partner);
            //const p = this.pos.get_order?.()?.get_partner?.() || null;
            if (!partner) return false;
            const Is_employee =  this.orm.call(
                "hr.employee","search_read",
                [[["work_contact_id","=",partner.id]],
                ["id","name"]
                ],
                {limit:1}
            );
            console.log("Is_employee",Is_employee)
            return !!(Is_employee?.length);
            this.env.bus.trigger("trigger-discount", { pc: 10 });
            // console.log("this.pos.Sale_type",this.pos.Sale_type);
            // this.pos.Sale_type = "Reembolso";
            // console.log("this.pos.Sale_type",this.pos.Sale_type);
            // const { updated } =  this.orm.call(
            //     "loyalty.card",
            //     "sync_source_order_by_posref",
            //     [],                 // args
            //     { limit: 1000 }     // kwargs opcional
            // );

            // console.log("loyalty.cards actualizados:", updated);
            //console.log(this.pos.pos_session.user_id)
            //console.log(this.pos.get_cashier()?.id )
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
    },

    async clickReembolso(){
        const { confirmed, payload } = await this.popup.add(MaskedInputPopup,{
            resolve: (result) => {
                console.log("Popup cerrado:", result);
            }
        });


        // if (confirmed) {
        //     alert("C")
        // }

        // const { confirmed, payload } = await this.popup.add(TextInputPopup, {
        //     title: _t("Reembolso por Ticket"),
        //     body: _t("Ingresa el número de ticket (pos_reference)."),
        //     placeholder: "S0001-001-0001",
        //     confirmText: _t("Buscar"),
        //     cancelText: _t("Cancelar"),
        //     inputProps: {
        //     onInput: (e) => {
        //         let input = e.target;
        //         let raw = input.value.replace(/[^0-9]/g, "").slice(0, 12); // Solo números
        //         let formatted = "S";

        //         if (raw.length > 0) formatted += raw.slice(0, 4);
        //         if (raw.length >= 5) formatted += "-" + raw.slice(4, 7);
        //         if (raw.length >= 8) formatted += "-" + raw.slice(7, 11);

        //         // Evita sobrescribir si el usuario borra
        //         input.value = formatted;

        //         // Reposiciona el cursor al final
        //         input.setSelectionRange(formatted.length, formatted.length);
        //     },
        //     maxlength: 17,
        //     },
        // });


        if (!confirmed || !payload) return;

        // Buscar la orden original
        const orderNumber = "Orden " + payload;
        const orders = await this.orm.call("pos.order", "search_read", [
            [["pos_reference", "=", orderNumber]],
            ["id", "pos_reference", "partner_id", "fiscal_position_id", "name"]
        ], { limit: 1 });


        if (!orders || orders.length === 0) {
            this.popup.add(ErrorPopup, {
            title: "Orden no encontrada",
            body: `No se encontró la orden ${orderNumber}`,
            });
            return;
        }

        const order = orders[0];
        console.log("Orden encontrada:", order);

        // ✅ VERIFICACIÓN 1: Evitar reembolsos de reembolsos
        const orderName = order.name || "";
        const posReference = order.pos_reference || "";

        // Si la orden original YA ES un reembolso, bloquear
        if (orderName.includes("REEMBOLSO") || 
            orderName.includes("DEVOLUCIÓN") || 
            orderName.includes("REFUND") ||
            posReference.includes("REEMBOLSO") ||
            posReference.includes("DEV") ||
            posReference.includes("REFUND")) {

            await this.popup.add(ErrorPopup, {
                title: "No se puede reembolsar un reembolso",
                body: "Esta orden ya es un reembolso. No se puede reembolsar un reembolso existente.",
            });
            return;
        }

        // ✅ VERIFICACIÓN 2: Evitar múltiples reembolsos de la misma orden
        const refundKey = `refund_${orderNumber}`;
        const existingRefund = localStorage.getItem(refundKey);

        if (existingRefund) {
            const refundDate = new Date(parseInt(existingRefund));
            await this.popup.add(ErrorPopup, {
                title: "Reembolso ya realizado",
                body: `Esta orden ya fue reembolsada el ${refundDate.toLocaleString()}. No se puede reembolsar nuevamente.`,
            });
            return;
        }

        // ✅ VERIFICACIÓN 3: Buscar en base de datos si ya hay reembolsos
        try {
            // Buscar órdenes que referencien esta orden original
            const existingRefunds = await this.orm.call("pos.order", "search_read", [
                [
                    ["name", "ilike", order.pos_reference],
                    "|",
                    ["name", "ilike", "REEMBOLSO"],
                    ["name", "ilike", "DEVOLUCIÓN"],
                    ["state", "in", ["paid", "done", "invoiced"]]
                ],
                ["id", "name", "pos_reference", "date_order"]
            ]);

            console.log("Reembolsos existentes en BD:", existingRefunds);

            if (existingRefunds && existingRefunds.length > 0) {
                await this.popup.add(ErrorPopup, {
                    title: "Reembolso ya realizado",
                    body: `Esta orden ya tiene ${existingRefunds.length} reembolso(s) en el sistema.`,
                });
                return;
            }
        } catch (error) {
            console.log("Error verificando reembolsos en BD:", error);
        }

        // ✅ MARCAR INMEDIATAMENTE para prevenir doble reembolso
        localStorage.setItem(refundKey, Date.now().toString());

        // Buscar líneas de la orden
        const orderLines = await this.orm.call("pos.order.line", "search_read", [
            [["order_id", "=", order.id]],
            [
            "id", "product_id", "qty", "price_unit", "discount",
            "tax_ids", "combo_parent_id", "combo_line_ids"
            ]
        ]);

        if (!orderLines.length) {
            this.popup.add(ErrorPopup, {
            title: "Sin líneas para reembolsar",
            body: "La orden no tiene líneas disponibles para reembolso.",
            });
            // Limpiar la marca si no hay líneas
            localStorage.removeItem(refundKey);
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
            // Limpiar la marca si no hay detalles reembolsables
            localStorage.removeItem(refundKey);
            return;
        }

        // orden de destino
        const refundOrder = this.pos.get_order()
        refundOrder.is_return = true;

        if (partner) refundOrder.set_partner(partner);

        const originalToRefundLineMap = new Map();

        // ✅ SOLUCIÓN para pack_lot_lines
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
            } catch (error) {
                console.error("Error agregando producto:", error);
            }
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
            [["pos_order_id", "=", order.id]],
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

        // ✅ MARCAR LA ORDEN ORIGINAL COMO REEMBOLSADA EN EL SISTEMA
        try {
            await this.orm.call("pos.order", "write", [[order.id], {
                note: `REEMBOLSADO - ${new Date().toLocaleString()}`
            }]);
        } catch (error) {
            console.log("No se pudo marcar la orden en BD:", error);
        }

        // Redirigir a pantalla de recibo
        this.pos.Sale_type = "Reembolso";
        this.pos.set_order(refundOrder);
        this.pos.Reembolso = true;
        this.pos.showScreen("PaymentScreen");

        // ✅ Limpiar el localStorage después de 2 horas (suficiente tiempo para completar el proceso)
        setTimeout(() => {
            localStorage.removeItem(refundKey);
        }, 2 * 60 * 60 * 1000);
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
            console.log("manda el id del user",check.id)
            // const currentEmployer_id = this.pos.get_cashier()?.id
            const advancedEmployeeIds = this.pos.config.advanced_employee_ids; // Lista de IDs
            const isAdvancedUser = advancedEmployeeIds.includes(check.id);

            console.log("Entro a validar con avanzado.", isAdvancedUser)
            if (isAdvancedUser && mode === "price")  {
                this.change_price()
            } 

            if (check.ok && mode === "discount")  {
                const order = this.posService.get_order();
                const partner = order?.get_partner?.() || order?.get_client?.() || null;
                let Is_employee = null

                if (partner) {
                    console.log("partner",partner);
                    console.log("Is_employee",Is_employee)
                    Is_employee = await this.orm.call(
                        "hr.employee","search_read",
                        [[["work_contact_id","=",partner.id]],
                        ["id","name"]
                        ],
                        {limit:1}
                    );
                }

                console.log("Is_employee",Is_employee)
                console.log("Is_employee?.length",Is_employee?.length)
                if (Is_employee?.length){
                    const cfgId = this.pos?.config?.id || false;
                    const employee_discount = await this.orm.call("pos.config", "get_employee_discount", [cfgId], {});
                    console.log(employee_discount)

                    await this.popup.add(ConfirmPopup, {
                        title: "Confirmación de descuento",
                        body: "¿Desea aplicar descuento al empleado?",
                    }).then(({ confirmed }) => {
                    if (confirmed) {
                        console.log("confimado")
                            this.env.bus.trigger("trigger-discount", { pc: 10 });
                        }
                    });
                    //this.env.bus.trigger("trigger-discount", { pc: 10 });
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
            body:  _t("Ingresa el precio."),
            //startingValue: String(current*1.16),
            // valida solo números con punto decimal (opcional)
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
    }
});
