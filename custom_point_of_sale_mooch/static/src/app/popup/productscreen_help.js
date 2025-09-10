/** @odoo-module **/
import { registry } from "@web/core/registry";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

export class HotkeyHelpPopup extends AbstractAwaitablePopup {
    static template = "custom_pos.HotkeyHelpPopup";
    static defaultProps = {
        title: "📖 Ayuda de Atajos",
        body: "",                // 👈 clave que usaremos en el XML (t-raw="props.body")
        confirmText: "Cerrar",
        cancelText: "",
    };
}

// Registra el popup por nombre para poder llamarlo como string:
registry.category("pos_popups").add("HotkeyHelpPopup", HotkeyHelpPopup);