/** @odoo-module **/
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";

 patch(PosStore.prototype, {
    //@override
     async after_load_server_data() {
        var res = await super.after_load_server_data(...arguments);
        
        const cfgId = this.config.id;
        //**Es el codigo de producto configurado en settings**
        this.product_changes_id = await this.env.services.orm.silent.call(
            "pos.config",
            "get_changes_product_id",
            [cfgId],
            {}
        );
        this.get_order()?.setProductChanges?.(this.product_changes_id);

        const loyalty_program_id = await this.orm.call("pos.config","get_loyalty_program_id", [cfgId], {});
        const product_voucher_id =  await this.env.services.orm.silent.call(
        "loyalty.reward",
        "search_read",
        [
            [["program_id", "=", loyalty_program_id]],            // domain
            ["discount_line_product_id"]                          // fields
        ],
        { limit: 1, order: "id asc" }                           // kwargs opcional
        );
        this.product_voucher_id = product_voucher_id[0].discount_line_product_id[0]
        this.get_order()?.setProductVaucherId?.(product_voucher_id[0].discount_line_product_id[0])
        return res;
    }
 });
