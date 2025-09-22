/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { Order } from "@point_of_sale/app/store/models";


patch(Order.prototype, {
    setup() {
        super.setup(...arguments);
        this.changes_codes = this.changes_codes || [];
        this.product_changes_id = Number(this.pos?.product_changes_id);
        this.voucher_code = this.voucher_code || null;
        this.product_voucher_id = Number(this.pos?.product_voucher_id);
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

  // setup() {
  //       this._super?.(...arguments);
  //       this.voucher_code = this.voucher_code || null;
  //   },
  
  // setVoucherCode(code) {
  //       this.voucher_code = code ? String(code) : null;
  // },


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

            let shortName = line.productName.substring(0, 20); 
            if (code && prod.id != oline_.pos.product_changes_id)  shortName += ` - ${code}` ; 
           
            // detecto si el producto es un cambio.
            if (prod.id === oline_.pos.product_changes_id) shortName += " " + oline_.order.changes_codes;
          
            // detecto si el producot es un vale
            if (oline_.order.voucher_code && prod.id === oline_?.order?.product_voucher_id ) shortName += oline_.order.voucher_code;

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
        const base = Array.isArray(this.new_coupon_info) && this.new_coupon_info.length
          ? this.new_coupon_info
          : [{
              // fallback: arma 1 cupón si no hay nada en this.new_coupon_info
              code: this.voucher_code || "",
              program_name: "Vales",
              expiration_date: new Date().toISOString().slice(0, 10) + 30,   // o una fecha real si la tienes
        }];
        r.new_coupon_info = base
      }

    return r;
  },

});
