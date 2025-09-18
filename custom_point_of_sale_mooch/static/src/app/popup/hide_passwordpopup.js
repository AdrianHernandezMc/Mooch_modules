/** @odoo-module **/
import { TextInputPopup } from "@point_of_sale/app/utils/input_popups/text_input_popup";

// Reutiliza la lógica del TextInputPopup, pero renderiza con nuestro template
export class PasswordInputPopup extends TextInputPopup {}
PasswordInputPopup.template = "custom_point_of_sale_mooch.PasswordInputPopup";