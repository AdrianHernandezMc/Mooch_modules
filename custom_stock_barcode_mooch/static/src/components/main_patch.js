/** @odoo-module **/

import MainComponent from "@stock_barcode/components/main"; 
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { InputDialog } from "./input_dialog"; 

patch(MainComponent.prototype, {

    // --- CONTADOR ---
    get totalStats() {
        let totalDone = 0;
        const lines = this.env.model.groupedLines || [];
        for (const line of lines) {
            const lineDone = this.env.model.getQtyDone(line) || 0;
            totalDone += lineDone;
        }
        return { done: parseFloat(totalDone.toFixed(2)) };
    },

    // --- BOTONES ---
    async onSaveSimple() {
        console.log(">>> Mooch: Guardado Simple");
        try {
            await this.env.model.save();
            this.env.services.notification.add(_t("Guardado."), { type: 'success' });
        } catch (error) {
            this.env.services.notification.add(_t("Error al guardar."), { type: 'danger' });
        }
    },

    async onSaveWithPopup() {
        await this._askRackAndProcess(false);
    },

    async onApplyWithPopup(ev) {
        ev.stopPropagation();
        await this._askRackAndProcess(true);
    },

    // --- POPUP ---
    async _askRackAndProcess(shouldApply) {
        // 1. Guardar para tener IDs reales
        await this.env.model.save();

        const lines = this.env.model.groupedLines || [];
        if (lines.length === 0) {
            this.env.services.notification.add(_t("No hay productos."), { type: 'warning' });
            return;
        }

        const title = shouldApply ? _t("Confirmar Rack y Validar") : _t("Guardar Rack (Pausa)");

        this.env.services.dialog.add(InputDialog, {
            title: title,
            confirm: async (areaName) => {
                if (!areaName || areaName.trim() === "") {
                    this.env.services.notification.add(_t("El Rack es obligatorio."), { type: 'danger' });
                    return;
                }
                const success = await this._assignAreaToAllLines(areaName);

                if (success && shouldApply) {
                    console.log(">>> Ejecutando Apply...");
                    await this.env.model.apply();
                } else if (success) {
                    this.env.services.notification.add(_t("Información guardada."), { type: 'success' });
                }
            }
        });
    },

    // --- ESCRITURA EN BD Y ACTUALIZACIÓN VISUAL ---
    async _assignAreaToAllLines(areaName) {
        try {
            // A. Detectar modelo
            let targetModel = this.env.model.resModel;
            if (targetModel === 'stock.picking') {
                targetModel = 'stock.move.line';
            }

            // B. Recolectar IDs válidos
            const lines = this.env.model.groupedLines || [];
            let validIds = [];

            // Recorremos para sacar IDs
            for (const line of lines) {
                const addIfValid = (id) => {
                    if ((typeof id === 'number' && id > 0) || (typeof id === 'string' && !isNaN(id))) {
                        validIds.push(parseInt(id));
                    }
                };
                if (line.lines && line.lines.length > 0) {
                   line.lines.forEach(sub => addIfValid(sub.id));
                } else {
                   addIfValid(line.id);
                }
            }
            validIds = [...new Set(validIds)];

            if (validIds.length === 0) {
                // Si no hay IDs reales, guardamos de nuevo por seguridad y salimos
                await this.env.model.save();
                return true; 
            }

            // C. ESCRIBIR EN BASE DE DATOS (Backend)
            await this.orm.write(targetModel, validIds, {
                quant_rack_area: areaName
            });
            
            // D. ACTUALIZACIÓN VISUAL (Frontend)
            // En lugar de llamar a updateState(), actualizamos manualmente los objetos en memoria
            for (const line of lines) {
                // Actualizamos la propiedad en la línea principal
                line.quant_rack_area = areaName;
                
                // Si es un grupo, actualizamos las sublíneas también
                if (line.lines && line.lines.length > 0) {
                    line.lines.forEach(sub => sub.quant_rack_area = areaName);
                }
            }

            // Forzamos a Odoo a repintar la pantalla con los nuevos datos
            this.render();

            return true;
        } catch (error) {
            console.error(">>> ERROR CRÍTICO asignando área:", error);
            this.env.services.notification.add(_t("Error técnico al escribir área."), { type: 'danger' });
            return false;
        }
    }
});