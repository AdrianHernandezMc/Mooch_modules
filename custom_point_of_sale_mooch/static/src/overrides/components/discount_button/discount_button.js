/** @odoo-module **/
import { DiscountButton } from "@pos_discount/overrides/components/discount_button/discount_button";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
// Asegúrate de que esta ruta sea correcta en tu sistema
import { PasswordInputPopup } from "@custom_point_of_sale_mooch/app/popup/hide_passwordpopup";
import { _t } from "@web/core/l10n/translation";

patch(DiscountButton.prototype, {
    // 1. Mantenemos tu validación de seguridad
    async click() {
        const { orm } = this.env.services;

        // --- INICIO DE TU LÓGICA DE SEGURIDAD ---
        const { confirmed, payload } = await this.popup.add(PasswordInputPopup, {
            title: _t("Contraseña de supervisor"),
            body: _t("Ingresa el NIP del Gerente de Ventas:"),
            confirmText: _t("Validar"),
            cancelText: _t("Cancelar"),
        });

        if (!confirmed || !payload) return;

        const nip = String(payload).trim();
        if (!nip) return;

        let check;
        try {
            check = await orm.call("hr.employee", "check_pos_nip", [nip], {});
        } catch (e) {
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t("No se pudo conectar con el servidor."),
            });
            return;
        }

        const advancedEmployeeIds = this.pos.config.advanced_employee_ids || [];
        const isAdvancedUser = check && advancedEmployeeIds.includes(check.id);

        if (!isAdvancedUser) {
            await this.popup.add(ErrorPopup, {
                title: _t("Acceso Denegado"),
                body: _t("NIP incorrecto o usuario sin permisos de supervisor."),
            });
            return;
        }

        const order = this.pos.get_order();
        // Validamos si ya hay líneas con descuento (para no sobreescribir accidentalmente)
        const discountLines = order ? order.get_orderlines().filter(l => l.get_discount() > 0) : [];

        if (discountLines.length > 0) {
            await this.popup.add(ErrorPopup, {
                title: _t("Operación Inválida"),
                body: _t("Ya existen líneas con descuento. Elimínelos o limpie la venta antes de aplicar un global."),
            });
            return;
        }
        // --- FIN DE TU LÓGICA DE SEGURIDAD ---

        // Llamamos al original para que muestre el popup de "¿Qué porcentaje desea?"
        // Al confirmar ese popup, Odoo llamará internamente a 'apply_discount'
        await super.click(); 
    },

    // 2. CAMBIAMOS CÓMO SE APLICA EL DESCUENTO
    // Esta función reemplaza totalmente la lógica nativa de Odoo de crear una línea negativa
    async apply_discount(pc) {
        const order = this.pos.get_order();
        const lines = order.get_orderlines();

        // Recorremos línea por línea y aplicamos el porcentaje directo al producto
        for (const line of lines) {
            // Opcional: Evitar aplicar descuento a las propinas si usas el módulo de propinas
            if (line.get_product().id === this.pos.config.tip_product_id?.[0]) {
                continue;
            }

            // Aplicamos el descuento (pc es el valor ingresado, ej: 10)
            // Esto actualiza el precio y los impuestos automáticamente en esa línea
            line.set_discount(pc);
        }
    },
});