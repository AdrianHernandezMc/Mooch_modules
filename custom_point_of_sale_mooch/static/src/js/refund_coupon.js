/** @odoo-module **/
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
const _superSetup = TicketScreen.prototype.setup;

patch(TicketScreen.prototype, {
    setup() {
        this.pos = useService("pos");
        this.rpc = useService("rpc");
        this.orm = useService("orm");
        this.pos.activate_changes = useState({ value: false });
        //this.poss = usePos();
        _superSetup.apply(this, arguments);
    },

    async onClickTicketExchange() {
        this.clearOrderlines()
        const destinationOrder = this.pos.get_order();

        if (destinationOrder) {
                this.pos.set_order(destinationOrder);
                const partner = this.getSelectedPartner();       
                const refundDetails = this._getRefundableDetails(partner);
                const taxById = Object.fromEntries(this.pos.taxes.map(t => [t.id, t]));
                const includeTax = this.pos.config.iface_tax_included;

                if (!refundDetails.length) {
                    return alert("selecciona un articulo")
                }

                let refund_codes = "Codes: "
                for (const rd of refundDetails) {
                  const pid = rd?.orderline?.productId;
                  const prod = this.pos.db.get_product_by_id?.(pid);
                  if (!refund_codes.includes(prod?.default_code)){
                      refund_codes = refund_codes + " - [" + prod?.default_code + "]" || "";
                      
                  }
                }

                let totalRefund = refundDetails.reduce((sum, detail) => {
                  const netPrice = detail.orderline.price / 1.16;    // sin impuestos
                  const qty      = detail.qty;

                  let unitTax = 0;
                  if (includeTax) {
                      for (const taxId of detail.orderline.tax_ids) {
                        const tax = taxById[taxId];
                        if (!tax) continue;

                        if (tax.amount_type === 'percent') {
                          // Ej. 16 %  → tax.amount = 16
                          unitTax += netPrice * (tax.amount / 100);
                        } else if (tax.amount_type === 'fixed') {
                          // Importe fijo por unidad
                          unitTax += tax.amount;
                        }
                      }
                  }

                  const unitTotalIncl = netPrice + unitTax;
                  return sum + unitTotalIncl * qty;
                }, 0);
                
                totalRefund = Math.round(totalRefund);
                totalRefund =  totalRefund.toFixed(2)

                if (totalRefund <= 0) {
                  alert("selecciona un arcitulo")
                  return
                }
                
                let ordername = refundDetails[0].orderline.orderUid
              //crea una lines de cambio en la tabla de cambios.
                const origin_id = refundDetails.map(d => d.orderline.orderBackendId);
                const productId_origin =  refundDetails.map(d => d.orderline.productId);

                  // await this.orm.call(
                  //   'pos.changes',
                  //   'poschanges_links_pre',
                  //   [
                  //     origin_id[0],
                  //     destinationOrder.uid,
                  //     productId_origin,
                  //   ]
                  //   );
              // *****

                await ProductScreen.prototype._applyCoupon.call(this, totalRefund, ordername, refund_codes);
                this.pos.showScreen("ProductScreen");
                this.pos.activate_changes = true
                //this.pos.toRefundLines = {};            
               
                //const couponId = await this.createCoupon(destinationOrder,totalRefund);
        // } catch (error) {
        //     this.pos.toRefundLines = {};
        //     alert("Error al guardar reembolso: " + (error.message || "Hubo un error al guardar la orden de reembolso."));
        // }
      }
    },
});

