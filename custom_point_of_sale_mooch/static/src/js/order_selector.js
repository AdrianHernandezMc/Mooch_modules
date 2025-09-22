/** @odoo-module **/
import { Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, {

    setup() {
        super.setup(...arguments);
         this.changes = this.changes || [];
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.changes = json.changes || [];
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.changes = this.changes || [];
        return json;
    },

    // API de conveniencia para el front-end.
    addChange(change) {
        this.changes.push(change);
        this.trigger("change", { changes: this.changes });
    },
});