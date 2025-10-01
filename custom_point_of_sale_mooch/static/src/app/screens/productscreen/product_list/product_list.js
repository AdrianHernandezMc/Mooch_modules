/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ProductsWidget } from "@point_of_sale/app/screens/product_screen/product_list/product_list";

const _productsToDisplay = Object.getOwnPropertyDescriptor(ProductsWidget.prototype,"productsToDisplay");
const callOriginalGetter = _productsToDisplay?.get ? (ctx) => _productsToDisplay.get.call(ctx) : null;

patch(ProductsWidget.prototype, {
    get productsToDisplay() {
    // 1) con este codigo mantengo el objeto arra con su prototype

    let listprototype = callOriginalGetter ? callOriginalGetter(this) : [];
    
    function cloneWithUiName(p) {
        const clone = Object.create(Object.getPrototypeOf(p)); // <- mantiene métodos
        Object.assign(clone, p);

        //concateno el nombre y el codigo del product
        const code = (p.default_code || "").trim();
        const base = p.display_name || "";
        clone.display_name = code ? `${base} - [${code}]` : base;
        return clone;
    }
     
    listprototype = listprototype.map(cloneWithUiName);
    return listprototype
  },
});

