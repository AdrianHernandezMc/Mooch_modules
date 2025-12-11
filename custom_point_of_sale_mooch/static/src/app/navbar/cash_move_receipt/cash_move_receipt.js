/** @odoo-module **/

// 1. Importamos el componente ORIGINAL de Odoo
import { CashMoveReceipt } from "@point_of_sale/app/navbar/cash_move_popup/cash_move_receipt/cash_move_receipt";
import { patch } from "@web/core/utils/patch";

// 2. MODIFICAMOS LAS PROPS DIRECTAMENTE EN LA CLASE ORIGINAL
// Esto es lo que soluciona el error "Invalid props".
// Le decimos a Odoo: "Acepta también estos campos nuevos".
CashMoveReceipt.props = {
    ...CashMoveReceipt.props, // Mantenemos las props originales (reason, date, etc.)
    sessionOpener: { type: String, optional: true },
    responsable: { type: String, optional: true },
    isCashOut: { type: Boolean, optional: true },
    posName: { type: String, optional: true },
};

// 3. PARCHEAMOS LA PLANTILLA
// Le decimos que use TU diseño XML en lugar del original
patch(CashMoveReceipt, {
    template: "custom_point_of_sale_mooch.CashMoveReceipt",
});