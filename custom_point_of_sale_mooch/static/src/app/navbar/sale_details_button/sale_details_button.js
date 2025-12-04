/** @odoo-module */

import { SaleDetailsButton as OriginalSaleDetailsButton } from "@point_of_sale/app/navbar/sale_details_button/sale_details_button";
import { useService } from "@web/core/utils/hooks";
import { renderToElement } from "@web/core/utils/render";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class SaleDetailsButton extends OriginalSaleDetailsButton {
    static template = "point_of_sale.SaleDetailsButton";
    
    setup() {
        super.setup();
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.hardwareProxy = useService("hardware_proxy");
    }
    
    async onClick() {
        try {
            // Llamamos al Python
            const saleDetails = await this.orm.call(
                "report.point_of_sale.report_saledetails",
                "get_sale_details",
                [false, false, false, [this.pos.pos_session.id]]
            );

            // Preparar datos finales
            const allData = {
                ...saleDetails,
                pos: this.pos,
                company_logo_base64: this.pos.company_logo_base64,
                date: new Date().toLocaleString(),
                formatCurrency: this.env.utils.formatCurrency,
            };

            // Renderizar
            const report = renderToElement("point_of_sale.SaleDetailsReport", allData);
            
            // Imprimir
            const { successful, message } = await this.hardwareProxy.printer.printReceipt(report);
            if (!successful) {
                await this.popup.add(ErrorPopup, { title: message.title, body: message.body });
            }

        } catch (error) {
            console.error(error);
            await this.popup.add(ErrorPopup, { title: "Error", body: "Revisa la consola" });
        }
    }
}