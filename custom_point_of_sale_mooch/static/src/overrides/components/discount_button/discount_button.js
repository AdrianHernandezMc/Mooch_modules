/** @odoo-module **/
import { DiscountButton } from "@pos_discount/overrides/components/discount_button/discount_button";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { PasswordInputPopup } from "@custom_point_of_sale_mooch/app/popup/hide_passwordpopup";
import { _t } from "@web/core/l10n/translation";

patch(DiscountButton.prototype, {
    async click() {
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

        const order = this.pos.get_order();
        const discountLines = order ? order.get_orderlines().filter(l => l.discount > 0) : [];

        if (discountLines.length) {
            this.popup.add(ErrorPopup, {
                title: "Descuentos",
                body: "Ya exite un desuento en la venta",
            });
            return;
        }
        await super.click(); // 🟢 conserva la lógica original
    },
});
