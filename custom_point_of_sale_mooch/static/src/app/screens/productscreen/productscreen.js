/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { TextInputPopup } from "@point_of_sale/app/utils/input_popups/text_input_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { useService } from "@web/core/utils/hooks";
import { HotkeyHelpPopup } from "@custom_point_of_sale_mooch/app/popup/productscreen_help";
import { registry } from "@web/core/registry";
import { markup } from "@odoo/owl";

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
            console.log('pos_popups →', registry.category('pos_popups').getAll())
            console.log("HotkeyHelpPopup props:", this.props);
              await popup.add(HotkeyHelpPopup, {
                title: "📖 Ayuda de Atajos",
                body: markup(`
                    <div style="text-align:left;">
                    <p><b>Alt + H</b> → Ayuda</p>
                    <p><b>Alt + P</b> → Activa de precios</p>
                    <p><b>Alt + T</b> → Limpiar líneas de venta</p>
                    <p><b>Alt + D</b> → Activa descuento</p>
                    <p><b>Alt + G</b> → Activa ventas guardadas</p>
                    </div>`),
            });
        });
        
        // **************   para hacer pruebad en productscreen  *******************
        useHotkey("alt+x", (ev) => {
            const order = this.pos.order()
            console.log("order", order);
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

    get productsToDisplay() {
        // 1) Obtener el resultado ORIGINAL (ya filtrado/ordenado por Odoo)
        const original = this._super?.(...arguments) || [];

        // 2) En algunos builds raros podría devolver IDs; conviértelos a objetos
        let list = original;
        if (typeof list?.[0] === "number") {
        const { db } = this.pos;                    // NO reasignar this.pos
        list = list.map((id) => db.get_product_by_id(id));
        }

        // 3) Decorar nombres (conservar orden original; no volver a ordenar)
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

    async change_price_desc(mode) {
        const { popup, orm } = this.env.services;
        
        // 1) Pedir NIP
        const nipRes = await popup.add(TextInputPopup, {
            title: "Autorización requerida",
            body: "Ingresa el NIP del Gerente de Ventas:",
            placeholder: "NIP",
            isPassword: true,
            confirmText: "Validar",
            cancelText: "Cancelar",
        });

        // Cancelado o vacío → no dejar entrar a "price"
        if (!nipRes.confirmed || !nipRes.payload) {
            return; 
        }

        const nip = String(nipRes.payload).trim();
        if (!nip) return;

        // 2) Validar NIP en servidor
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
