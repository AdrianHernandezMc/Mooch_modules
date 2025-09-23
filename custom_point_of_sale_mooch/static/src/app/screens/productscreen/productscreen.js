/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { TextInputPopup } from "@point_of_sale/app/utils/input_popups/text_input_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { useService } from "@web/core/utils/hooks";
import { HotkeyHelpPopup } from "@custom_point_of_sale_mooch/app/popup/productscreen_help";
import { markup } from "@odoo/owl";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { PasswordInputPopup } from "@custom_point_of_sale_mooch/app/popup/hide_passwordpopup";

// function addMonthtoday(date = new Date()) {
//     const y = date.getFullYear();
//     const m = date.getMonth();  // 0=Ene
//     const d = date.getDate();
//     const targetM = m + 1;
//     const targetY = y + Math.floor(targetM / 12);
//     const targetMi = targetM % 12;
//     const daysInTarget = new Date(targetY, targetMi + 1, 0).getDate(); // último día del mes destino
//     const day = Math.min(d, daysInTarget);
// return new Date(targetY, targetMi, day);
// }

const _superSetNumpadMode = ProductScreen.prototype.onNumpadClick;

//Parcheamos el método que invoca el botón "Precio" (cambia el modo del Numpad)
patch(ProductScreen.prototype, {
    
    setup() {
        super.setup(...arguments);
        const popup = useService("popup");

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
            //**********        no borrar      ********/
            // const { confirmed, payload } =  this.popup.add(PasswordInputPopup, {
            //     title: _t("NIP"),
            //     body: _t("Ingresa el NIP del Gerente de Ventas:"),
            //     confirmText: _t("Validar"),
            //     cancelText: _t("Cancelar"),
            // });
            console.log("correcoupn",Object.values(this.currentOrder.couponPointChanges))
        
        });
        
        // Alt + g para entrar a las ordenes guardadas
        useHotkey("alt+g", (ev) => {
            // console.log(this.TICKET_SCREEN_STATE)
            // const TICKET_SCREEN_STATE =  this.TICKET_SCREEN_STATE
            
            // TICKET_SCREEN_STATE.forEach(l => {
            //     l.ui.fiter = "SYNCED"
            // });
            // console.log("this.TICKET_SCREEN_STATE)",this.TICKET_SCREEN_STATE)
            this.pos.showScreen("TicketScreen");
        });
    },

    async onMounted() {
        await this.clear_pay_method()
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

    async createvale_screen(amount_total){
        console.log("amount_total",amount_total)
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
            amount_total = amount_total * -1
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

        console.log(Object.values(this.currentOrder.couponPointChanges))

        order.add_product(product, {
            quantity: 1,
            price:    amount_total,
            merge:    false,
            uom_id:   [1, 'Unidad']
        });

        if (!this.currentOrder.couponPointChanges || Array.isArray(this.currentOrder.couponPointChanges)) {
            this.currentOrder.couponPointChanges = {};
        }
        const changes = this.currentOrder.couponPointChanges;
        // 2) Intenta encontrar una entrada existente por program_id
        let entry =
        Object.values(changes).find(v => Number(v?.program_id) === Number(loyalty_program_id));

        // 3) Si NO existe, créala y guárdala con una clave estable
        if (!entry) {
        entry = {
            points: amount_total,
            code: defaults.code,
            program_id: loyalty_program_id,
            coupon_id: -2,
            appliedRules: [loyalty_program_id],
            expiration_date: new Date() + 30,   // ajusta si necesitas
        };
        // Usa el program_id como clave (string). Si no puedes, usa un uuid/timestamp.
        const key = String(loyalty_program_id);
        changes[key] = entry;
        }

        // 4) Modifica los campos deseados
        //entry.points  = NEW_POINTS;
        //entry.barcode = NEW_BARCODE;

        //console.log("✅ couponPointChanges:", this.currentOrder.couponPointChanges);


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
        
        // const line = order.get_selected_orderline();
        // if (line) {
        //     const unit = line.get_unit_price();
        //     const p = line.get_all_prices(); // { priceWithTax, priceWithoutTax, price, tax, ... }
        //     console.log("unit:", unit, "priceWithTax:", p.priceWithTax, "priceWithoutTax:", p.priceWithoutTax);
        // }

        // const lines = (order?.get_orderlines?.() || []).filter(
        //     (l) => l?.product?.id === order.product_voucher_id
        // );
        // console.log("lines",lines)
        // // 2a) suma cantidades
        // let totalWithTax = (lines || []).reduce((acc, l) => {
        //     const p = l.get_all_prices?.();
        //     return acc + (p?.priceWithTax ?? 0);
        // }, 0);
        // totalWithTax = totalWithTax.toFixed(2);
        // console.log("totalQty",totalWithTax);

        // /********* Agrego el vale al programa */
        // //const cfgId = this.pos.config.id; 
        // //const loyaty_program_id = await this.orm.call("pos.config","get_loyalty_program_id", [cfgId], {});
        // const companyId = this.pos.company?.id;   // ← ID de la compañía
        // const exp = addMonthtoday(new Date());
        // const dateAddOneMonth = exp.toISOString().slice(0, 10); // "YYYY-MM-DD"
        // //const order   = this.currentOrder;
        // const partner = order.client;
        // //const partnerId = partner ? partner.id : false;
       
        // console.log("loyaty_program_id",loyaty_program_id);

        // // Preparas el diccionario con todos los campos
        // const couponData = {
        //   program_id:          loyaty_program_id,
        //   company_id:          companyId,                // compañía
        //   partner_id:          partner?.id || false,
        //   code:                defaults.code,
        //   expiration_date:     dateAddOneMonth,
        //   points:              amount_total,
        //   source_pos_order_id: order.id,         // referenciamos la venta
        // };

        // console.log("couponData",couponData)
        // const couponId = await this.orm.create(
        //   "loyalty.card",    // modelo
        //   [ couponData ]     // aquí sí va un solo nivel de array
        // );
    },

    async change_price_desc(mode) {
        const { popup, orm } = this.env.services;
        const nipRes = await popup.add(TextInputPopup, {
            title: "Captura Autorizacion",
            body: "Ingresa el NIP del Gerente de Ventas:",
            placeholder: "NIP",
            inputType: "password",
           inputProps: { type: "password", autocomplete: "off" }, // ⬅️ fuerza tipo 
            //isPassword: true,
            confirmText: "Validar",
            cancelText: "Cancelar",
        });

        if (!nipRes.confirmed || !nipRes.payload) {
            return; 
        }

        const nip = String(nipRes.payload).trim();
        if (!nip) return;

        let check = { ok: false, name: "" };
        try {
            check = await orm.call("hr.employee", "check_pos_nip", [nip], {});

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
            if (!check?.ok) {
                await popup.add(TextInputPopup, {
                    title: "Acceso denegado",
                    body: "NIP inválido o el empleado no es 'Gerente Ventas'.",
                    startingValue: "",
                    confirmText: "OK",
                });
            return; 
        }
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
