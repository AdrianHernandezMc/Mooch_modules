/** @odoo-module */

import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { renderToElement } from "@web/core/utils/render";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { useService } from "@web/core/utils/hooks";

patch(ClosePosPopup.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.hardwareProxy = useService("hardware_proxy");
        this.popup = useService("popup");
    },

    /**
     * PROCESO DE CIERRE REAL (CORTE Z)
     * 1. Genera los datos.
     * 2. Imprime el ticket físico.
     * 3. Ejecuta el cierre oficial de Odoo (Asientos, Seguridad, Etc).
     */
    async confirm() {
        try {
            // -------------------------------------------------------------
            // PASO 1: GENERAR LOS DATOS DEL REPORTE
            // -------------------------------------------------------------
            // Llamamos al mismo método Python que usas para el Corte X
            const saleDetails = await this.orm.call(
                "report.point_of_sale.report_saledetails",
                "get_sale_details",
                [false, false, false, [this.pos.pos_session.id]]
            );

            // Preparamos los datos para la plantilla XML
            // Activamos is_z_report: true para que el título diga "CORTE FINAL (Z)"
            // y muestre los Folios y el Arqueo completo.
            const allData = {
                ...saleDetails,
                pos: this.pos,
                company_logo_base64: this.pos.company_logo_base64,
                date: new Date().toLocaleString(),
                formatCurrency: this.env.utils.formatCurrency,
                is_z_report: true, 
            };

            // -------------------------------------------------------------
            // PASO 2: IMPRIMIR EL TICKET FÍSICO
            // -------------------------------------------------------------
            const report = renderToElement("point_of_sale.SaleDetailsReport", allData);
            
            // Enviamos a la impresora
            const { successful, message } = await this.hardwareProxy.printer.printReceipt(report);
            
            // Si la impresora falla, avisamos pero NO detenemos el cierre
            if (!successful) {
                await this.popup.add(ErrorPopup, { 
                    title: message?.title || "Aviso de Impresora", 
                    body: "El reporte Z no se pudo imprimir automáticamente. Revisa la impresora.\n\nLa sesión se cerrará de todos modos." 
                });
            }

            // -------------------------------------------------------------
            // PASO 3: EJECUTAR EL CIERRE REAL DE ODOO
            // -------------------------------------------------------------
            // Esta línea estaba comentada en el modo debug.
            // Ahora la activamos para que Cierre la Sesión y genere Pólizas.
            await super.confirm();

        } catch (error) {
            console.error("Error en Corte Z:", error);
            // Si hay un error grave (ej. caída de internet), mostramos popup y NO cerramos.
            await this.popup.add(ErrorPopup, { 
                title: "Error al Cerrar", 
                body: "Ocurrió un error al procesar el cierre. Por favor verifica tu conexión o contacta a soporte." 
            });
        }
    }
});