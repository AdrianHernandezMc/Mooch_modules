/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { Order } from "@point_of_sale/app/store/models";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

function daysInMonth(date) {
  const y = date.getFullYear();
  const m = date.getMonth();         // 0=enero, 11=diciembre
  return new Date(y, m + 1, 0).getDate();  // último día del mes → # de días
}

const originalPay = Order.prototype.pay;

patch(Order.prototype, {
    setup() {
        super.setup(...arguments);
        this.changes_codes = this.changes_codes || [];
        this.product_changes_id = Number(this.pos?.product_changes_id);
        this.voucher_code = null;
        this.product_voucher_id = Number(this.pos?.product_voucher_id);
    },
  
    // Funciones auxiliares de totales
    get_total_with_tax() {
        let total = 0;
        this.orderlines.forEach(line => { total += line.get_price_with_tax(); });
        return Math.round(total);
    },
    get_total_without_tax() {
        let subtotal = 0;
        this.orderlines.forEach(line => { subtotal += line.get_unit_price() * line.quantity; });
        return Math.round(subtotal);
    },

    setProductChanges(id) { this.product_changes_id = Number(id); },
    setProductVaucherId(id) { this.product_voucher_id = Number(id); },
    setExchangeNote(string) {
        let s = string == null ? "" : String(string);
        s = s.normalize("NFKC").trim();
        this.changes_codes = s || null;
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.changes_codes = this.changes_codes || [];
        json.product_changes_id = this.product_changes_id ?? null;
        json.voucher_code = this.voucher_code ?? null;
        json.product_voucher_id = this.product_voucher_id ?? null;
        return json;
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.changes_codes = json.changes_codes || [];
        this.product_changes_id = Number(json?.product_changes_id);
        this.voucher_code = json.voucher_code ?? null;
        this.product_voucher_id = json.product_voucher_id ?? null;
    },

    export_for_printing() {
        const r = super.export_for_printing(...arguments);
        
        // Ajustes de totales y redondeo
        r.tax_details = [];
        r.amount_total = r.amount_total + r.rounding_applied;
        r.rounding_applied = null;
        r.order_barcode = this.pos_reference || this.name || "000000000000";

        // --- 1. Artículos vendidos ---
        const lines = this.get_orderlines?.() || [];
        r.qty_articles = lines.reduce((a, l) => a + Math.max(l.quantity ?? 0, 0), 0);

        // --- 2. Modificación de Líneas de Productos (CORRECCIÓN DE CEROS) ---
        const olines = this.get_orderlines?.() || [];
        
        r.orderlines = (r.orderlines || []).map((line, idx) => {
            const oline_ = olines[idx];  // Objeto original del modelo (tiene los métodos de cálculo)
            const prod = oline_?.product;
            const code = prod?.default_code || "";

            // A. CÁLCULO EXPLÍCITO DE PRECIOS (Para evitar el $ 0.00)
            // get_display_price(): Devuelve el Total de la línea (Cantidad * Precio - Descuento + Impuesto)
            const total_real = oline_.get_display_price(); 
            // get_unit_display_price(): Devuelve el Precio Unitario real
            const unit_real  = oline_.get_unit_display_price();

            // B. FORMATEO DEL PRECIO UNITARIO A TEXTO (Para "5.00 x 346.00")
            // Usamos el valor real calculado para asegurar que sea correcto
            line.price = unit_real.toFixed(2); 

            // C. CONSTRUCCIÓN DEL NOMBRE (Nombre + Código)
            let shortName = line.productName.substring(0, 35); 
            
            // Agregar código si no es producto de cambio
            if (code && prod.id != this.pos.product_changes_id) {
                shortName += ` - ${code}`;
            }
           
            // Agregar nota de cambio si aplica
            if (prod.id === this.pos.product_changes_id) {
                shortName += " " + (this.changes_codes || "");
            }

            // Retornamos la línea con los VALORES FORZADOS
            return { 
                ...line, 
                default_code: code, 
                productName: shortName,
                product_name: shortName, // Compatibilidad XML
                unit: "",
                
                // AQUÍ ESTÁ LA SOLUCIÓN A LOS CEROS:
                price_display: total_real,      // Forzamos el total correcto para la columna derecha
                price_unit_val: unit_real,      // Guardamos el unitario numérico para el descuento
            }; 
        });

        // --- 3. Líneas de Pago ---
        const Paymentsline = this.get_paymentlines?.() || [];
        const Printpaylines = r.paymentlines || [];

        Printpaylines.forEach((pline, idx) => {
            const pl = Paymentsline[idx]?.transaction_id || "";
            if (pl) {
                pline.name = pline.name + " - " + pl ;
                pline.transaction_id = pl;
            }
        });
      
        // --- 4. Cupones / Vales ---
        const voucher_code = lines[0]?.order?.voucher_code ?? null;
        if (!voucher_code){
            r.new_coupon_info = [];
        } else {
            let dateexpire = new Date();
            dateexpire.setDate(dateexpire.getDate() + 30);  
            dateexpire = dateexpire.toISOString().slice(0, 10);
            
            r.new_coupon_info = [{
                code: this.voucher_code || "",
                program_name: "Vales",
                expiration_date: dateexpire,
            }];
        }
        
        r.sale_type = this.pos.Sale_type;
        
        return r;
    },

    pay() {
        if (this.pos.bloqueodecaja) {
             this.pos.env.services.popup.add(ErrorPopup, {
                title: _t("Bloqueo de caja"),
                body: _t("Solicita el retiro de efectivo para desbloquear."),
            });
            return; 
        }
        return originalPay.call(this);
    },
});