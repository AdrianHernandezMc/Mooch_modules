/** @odoo-module */

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { renderToElement } from "@web/core/utils/render";
import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

export class SalesDetailReceiptButton extends Component {
    static template = "SalesDetailReceiptButton";

    setup() {
        this.pos = usePos();
        this.printer = useService("printer");
        this.popup = useService("popup");
        this.orm = useService("orm");
    }

    async onClick() {
        try {
            // 1. Obtenemos el ID de la sesión actual
            const sessionId = this.pos.pos_session.id;

            // 2. Llamada al Backend (Python)
            const result = await this.orm.call(
                "pos.session", 
                "get_sales_details_backend", 
                [[sessionId]]
            );

            const details = result.details;
            const grand_total = result.grand_total;
            
            // Verificamos si hay datos
            if (Object.keys(details).length === 0) {
                 this.popup.add(ErrorPopup, {
                    title: 'Sin información',
                    body: 'No hay ventas registradas en la base de datos para esta sesión.',
                });
                return;
            }

            // 3. Preparar datos para el Ticket
            const receiptData = {
                details: details,
                grand_total: grand_total,
                date: new Date().toLocaleString(),
                cashier: this.pos.get_cashier().name,
                // ======================================================================
                // CORRECCIÓN AQUÍ: Usamos this.env.utils.formatCurrency
                // ======================================================================
                formatCurrency: (amount) => this.env.utils.formatCurrency(amount),
            };

            // 4. Imprimir
            const receiptHtml = renderToElement('SalesDetailsReceipt', {
                props: receiptData
            });

            if (this.printer && this.printer.printReceipt) {
                 await this.printer.printReceipt(receiptHtml);
            } else {
                 await this.pos.hardwareProxy.printer.printReceipt(receiptHtml);
            }

        } catch (error) {
            console.error("Error obteniendo detalle de ventas:", error);
            this.popup.add(ErrorPopup, {
                title: 'Error',
                body: 'Hubo un error al consultar las ventas. Verifique su conexión.',
            });
        }
    }
}

// Registro en Navbar
Navbar.components = {
    ...Navbar.components,
    SalesDetailReceiptButton,
};