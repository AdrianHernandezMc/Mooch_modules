/** @odoo-module **/

import { registry } from "@web/core/registry";

const posModels = registry.category("pos_models");

// Extiende el modelo de métodos de pago del POS
posModels.add("pos.payment.method", {
  // 1) Declara el campo en el store del POS
  fields: {
    transaction_id: { type: "string" },           // ⚠️ Poco usual en método
    require_transaction_id: { type: "boolean" },  // ✅ Útil para UI
  },
  // 2) Métodos del "record" (no se exportan al backend en la orden)
  recordMethods: {
    set_transaction_id(v) {                        // Tendría poco sentido aquí
      this.transaction_id = true;
    },
  },
});
console.log("posModels",posModels);

