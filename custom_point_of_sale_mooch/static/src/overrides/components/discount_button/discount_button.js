/** @odoo-module **/
import { DiscountButton } from "@pos_discount/overrides/components/discount_button/discount_button";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { PasswordInputPopup } from "@custom_point_of_sale_mooch/app/popup/hide_passwordpopup";
import { _t } from "@web/core/l10n/translation";

patch(DiscountButton.prototype, {
    async click() {
        const { popup } = this.env.services;

        // 1. Validación de supervisor
        const { confirmed, payload } = await this.popup.add(PasswordInputPopup, {
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
    
        let check = { ok: false, name: "", id: null };
        
        try {
            check = await this.env.services.orm.call("hr.employee", "check_pos_nip", [nip], {});
        } catch (e) { 
            console.error("Error validando NIP:", e); 
            return; 
        }

        const advancedEmployeeIds = this.pos.config.advanced_employee_ids || []; 
        const isAdvancedUser = advancedEmployeeIds.includes(check.id);

        if (!isAdvancedUser){
             this.popup.add(ErrorPopup, {
                title: _t("Validacion supervisor"),
                body: _t("No es usuario supervisor"),
            });
            return;
        }

        // Verificar si ya hay descuentos en la orden
        const order = this.pos.get_order();
        if (!order) return;
        
        const configDiscount = this.pos.config.discount_product_id;
        const discountProductId = Array.isArray(configDiscount) ? configDiscount[0] : configDiscount;
        
        // Verificar si ya hay una línea de descuento global
        const existingGlobalDiscount = order.get_orderlines().find(line => 
            line.product && line.product.id === discountProductId
        );

        if (existingGlobalDiscount) {
            this.popup.add(ErrorPopup, {
                title: "Descuentos",
                body: "Ya existe un descuento global en la venta",
            });
            return;
        }

        // Guardar el número de líneas antes del descuento
        const linesBefore = order.get_orderlines().length;
        
        // Llamar al método original para crear la línea de descuento
        await super.click();
        
        // Esperar un momento para que se procese y luego actualizar el nombre
        setTimeout(() => {
            this._updateDiscountNameWithPercentage(linesBefore);
        }, 150);
    },

    /**
     * Actualiza el nombre de la línea de descuento con el porcentaje - VERSIÓN MEJORADA
     */
    _updateDiscountNameWithPercentage(linesBefore) {
        try {
            const order = this.pos.get_order();
            if (!order) {
                console.log("No hay orden activa");
                return;
            }

            const linesAfter = order.get_orderlines();
            
            // Verificar si se agregó una nueva línea
            if (linesAfter.length <= linesBefore) {
                console.log("No se agregó nueva línea de descuento");
                return;
            }
            
            // Obtener la línea de descuento (la última agregada)
            const discountLine = linesAfter[linesAfter.length - 1];
            
            // Verificar que es una línea de descuento
            const configDiscount = this.pos.config.discount_product_id;
            const discountProductId = Array.isArray(configDiscount) ? configDiscount[0] : configDiscount;
            
            if (!discountLine.product || discountLine.product.id !== discountProductId) {
                console.log("La última línea no es un descuento");
                return;
            }

            // Calcular el subtotal de todos los productos (excluyendo la línea de descuento)
            const productsLines = linesAfter.filter(line => 
                line.product && line.product.id !== discountProductId
            );
            
            let subtotal = 0;
            productsLines.forEach(line => {
                subtotal += line.get_display_price();
            });

            // Obtener el monto del descuento (en valor absoluto)
            const discountAmount = Math.abs(discountLine.get_display_price());
            
            // Calcular porcentaje - REDONDEADO A ENTERO SIN DECIMALES
            let percent = 0;
            if (subtotal > 0) {
                percent = (discountAmount / subtotal) * 100;
                // ✅ CAMBIO AQUÍ: Redondear al entero más cercano (sin decimales)
                percent = Math.round(percent);  // Solo esto, sin / 100
            }
            
            // Crear nuevo nombre
            const newName = `[DISC] Descuento Global (${percent}%)`;
            
            console.log(`🎯 Calculando descuento:`);
            console.log(`   - Subtotal productos: $${subtotal.toFixed(2)}`);
            console.log(`   - Monto descuento: $${discountAmount.toFixed(2)}`);
            console.log(`   - Porcentaje: ${percent}% (redondeado a entero)`);
            console.log(`   - Nuevo nombre: ${newName}`);
            
            // MÉTODO MEJORADO: Forzar actualización completa
            this._forceDiscountNameUpdate(discountLine, newName);
            
        } catch (error) {
            console.error("Error actualizando nombre del descuento:", error);
        }
    },

    /**
     * Método robusto para forzar la actualización del nombre del descuento
     */
    _forceDiscountNameUpdate(discountLine, newName) {
        try {
            // 1. Actualizar el nombre del producto en el objeto product
            if (discountLine.product) {
                discountLine.product.display_name = newName;
                discountLine.product.name = newName;
                discountLine.product.full_product_name = newName;
            }
            
            // 2. Actualizar en la línea
            discountLine.productName = newName;
            discountLine.full_product_name = newName;
            
            // 3. Actualizar cache del producto en la base de datos local del POS
            const productId = discountLine.product.id;
            const productInDb = this.pos.db.get_product_by_id(productId);
            if (productInDb) {
                productInDb.display_name = newName;
                productInDb.name = newName;
            }
            
            // 4. Métodos para forzar re-render
            // Opción A: Cambiar la cantidad (más efectivo)
            const currentQty = discountLine.get_quantity();
            discountLine.set_quantity(currentQty + 0.001);
            setTimeout(() => {
                discountLine.set_quantity(currentQty);
            }, 10);
            
            // Opción B: Disparar evento de cambio
            const order = this.pos.get_order();
            if (order && order.trigger) {
                order.trigger('line-change', discountLine);
                order.trigger('change', order);
            }
            
            // Opción C: Forzar actualización de impuestos
            if (order && order._updateTaxes) {
                order._updateTaxes();
            }
            
            // Opción D: Actualizar la UI del POS
            if (this.pos && this.pos.chrome && this.pos.chrome.widget) {
                // Esto puede variar según la versión
                this.pos.chrome.widget.update();
            }
            
            console.log(`✅ Nombre del descuento actualizado: ${newName}`);
            
        } catch (error) {
            console.error("Error en _forceDiscountNameUpdate:", error);
        }
    }
});