/** @odoo-module **/

import MainComponent from "@stock_barcode/components/main"; 
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(MainComponent.prototype, {
    
    // Calcula totales para cualquier modelo (Picking o Quant)
    get totalStats() {
        let totalDone = 0;
        
        // Obtenemos las líneas visibles
        const lines = this.env.model.groupedLines || [];

        for (const line of lines) {
            // El modelo interno de Odoo se encarga de saber qué campo leer
            // (qty_done o inventory_quantity)
            const lineDone = this.env.model.getQtyDone(line) || 0;
            totalDone += lineDone;
        }

        return {
            done: parseFloat(totalDone.toFixed(2)),
        };
    },

    async onSaveButton() {
        console.log(">>> Mooch: Botón Guardar presionado");
        try {
            await this.env.model.save();
            this.render(); 
            this.env.services.notification.add(_t("Progreso guardado correctamente."), {
                type: 'success',
                title: "Mooch",
                sticky: false,
            });
        } catch (error) {
            console.error(">>> Error en Mooch Save:", error);
            this.env.services.notification.add(_t("Error al guardar."), {
                type: 'danger',
            });
        }
    }
});