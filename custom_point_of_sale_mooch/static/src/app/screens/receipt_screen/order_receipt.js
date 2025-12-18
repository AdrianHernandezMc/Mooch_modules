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
  
  // redondeo el tota de la pantalla del product_screen
  get_total_with_tax() {
    let total = 0;
    this.orderlines.forEach(line => {
        total += line.get_price_with_tax();
    });
    return Math.round(total); // o parseFloat(total.toFixed(2)) si prefieres dos decimales
  },
  // redondeo el impuesto de la pantalla del product_screen
  get_total_without_tax() {
    let subtotal = 0;
    this.orderlines.forEach(line => {
        subtotal += line.get_unit_price() * line.quantity;
    });
    return Math.round(subtotal); // o parseFloat(subtotal.toFixed(2))
},

  setProductChanges(id) {
    this.product_changes_id = Number(id);
  },

  setProductVaucherId(id) {
    this.product_voucher_id = Number(id);
  },

  setExchangeNote(string) {
    let s = string == null ? "" : String(v);
    s = s.normalize("NFKC").trim(); //-- arregla texto, guiones,y caracteres extraños
    this.changes_codes = s || null;
  },

  export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.changes_codes = this.changes_codes || [];
        json.product_changes_id = this.product_changes_id ?? null;
        json.voucher_code = this.voucher_code ?? null
        json.product_voucher_id = this.product_voucher_id ?? null
        return json;
    },

  init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.changes_codes = json.changes_codes || [];
        this.product_changes_id = Number(json?.product_changes_id);
        this.voucher_code = json.voucher_code ?? null
        this.product_voucher_id = json.product_voucher_id ?? null
    },

  export_for_printing() {
    const r = super.export_for_printing(...arguments);
        r.tax_details = [];
        r.amount_total = r.amount_total + r.rounding_applied;
        r.rounding_applied = null;
        r.order_barcode = this.pos_reference || this.name || "000000000000";

    //---Articulos vendido -------
        const lines = this.get_orderlines?.() || [];
        const qty_articles_Pos = lines.reduce((a, l) => a + Math.max(l.quantity ?? 0, 0), 0);
        r.qty_articles = qty_articles_Pos;


    //--- modifica linea de articulos ------
        const olines = this.get_orderlines?.() || [];
        r.orderlines = (r.orderlines || []).map((line, idx) => {
            const oline_   = olines[idx];  //--emparejamos ids de  r.orderlines con olines
            const prod = oline_?.product;
            const code = prod?.default_code || "";

            //console.log("r.productName",r.productName)
            if (line.price_without_discount.length > 0){
              const price_without_discount = line.price_without_discount
              line.price_without_discount = line.price
              console.log("price",price_without_discount,"type",typeof price_without_discount)
              console.log(Math.round(Number(price_without_discount)))
              //line.price = String(Math.round(Number(price_without_discount)))
              let num = parseFloat(Math.round(price_without_discount.replace(/[^\d.-]/g, ''))) || 0;
              line.price = num.toFixed(2);
            }

            let shortName = line.productName.substring(0, 35); 
            if (code && prod.id != oline_.pos.product_changes_id)  shortName += ` - ${code}` ; 
           
            // detecto si el producto es un cambio.
            if (prod.id === oline_.pos.product_changes_id) shortName += " " + oline_.order.changes_codes;
          
            // detecto si el producot es un vale
            //if (oline_.order.voucher_code && prod.id === oline_?.order?.product_voucher_id ) shortName += oline_.order.voucher_code;

            return { ...line, 
                default_code: code, 
                productName: shortName,
                unit: "" }; 
        });
    //--- agreto las lineas de pago el transanction Id

        const Paymentsline = this.get_paymentlines?.() || [];
        const Printpaylines = r.paymentlines || [];

        Printpaylines.forEach((pline, idx) => {
            const pl = Paymentsline[idx]?.transaction_id || "";
            if (pl) {
            pline.name = pline.name + " - " + pl ;
            pline.transaction_id = pl;
          }
        });
      
    //--- Agrego lineas para la impesion del voucher 
        const voucher_code = olines[0]?.order?.voucher_code ?? null
        if (!voucher_code){
            r.new_coupon_info = [];
        }
        else {
          let dateexpire = new Date();            // hoy (Date)
          dateexpire.setDate(dateexpire.getDate() + 30);  
          dateexpire = dateexpire.toISOString().slice(0, 10);
          const base = 
            [{
                code: this.voucher_code || "",
                program_name: "Vales",
                expiration_date: dateexpire,   // o una fecha real si la tienes
          }];
          r.new_coupon_info = base
          console.log("base",base)
        }
        console.log("r.new_coupon_info",r.new_coupon_info)
        // Indico cual es el tipo de venta
        r.sale_type = this.pos.Sale_type
        
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
    // Ejecutar la lógica original si no hay bloqueo
    return originalPay.call(this);
  },
});
