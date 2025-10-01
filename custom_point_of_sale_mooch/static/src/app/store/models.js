/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { Product } from "@point_of_sale/app/store/models";

patch(Product.prototype, {
  
    getFormattedUnitPrice() {
        const rawPrice = this.get_display_price(); // obtiene el precio base
        const roundedPrice = Math.round(rawPrice); // redondea al entero más cercano
        const formattedUnitPrice = this.env.utils.formatCurrency(roundedPrice);

        if (this.to_weight) {
            return `${formattedUnitPrice}/${this.get_unit().name}`;
        } else {
            return formattedUnitPrice;
        }
    },
    
});