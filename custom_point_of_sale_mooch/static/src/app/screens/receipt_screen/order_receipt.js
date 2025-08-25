/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { Order } from "@point_of_sale/app/store/models";

patch(Order.prototype, {

  export_for_printing() {
    const r = super.export_for_printing(...arguments);
    
        r.tax_details = [];         // ← sin filas de impuestos
        r.amount_total = r.amount_total + r.rounding_applied
        r.rounding_applied = null

    //---Articulos vendido -------
    
        const lines = this.get_orderlines?.() || [];
        const qty_articles_Pos = lines.reduce((a, l) => a + Math.max(l.quantity ?? 0, 0), 0);
        r.qty_articles = qty_articles_Pos;

    //--- modifica linea de articulos ------
        
        //obtengo el codigo de cada artiuclo de la orden un y agrego a r.ordelines
        const olines = this.get_orderlines?.() || []; 
        
        r.orderlines = (r.orderlines || []).map((line, idx) => {
            const oline_   = olines[idx];  //--emparejamos ids de  r.orderlines con olines
            const prod = oline_?.product;
            const code = prod?.default_code || "";      // código interno (fallback vacío)

            let shortName = line.productName.substring(0, 20); 
            if (code) shortName += ` [${code}]`; 

            return { ...line, 
                default_code: code, 
                productName: shortName };     // ⬅️ ahora line.default_code existe
        });
    
    return r;
  },
});
