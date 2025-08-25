/** @odoo-module **/
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
const _superSetup = TicketScreen.prototype.setup;

patch(TicketScreen.prototype, {
    setup() {

        //this.popup = useService('popup');
        this.pos = useService("pos");
        this.rpc = useService("rpc");
        this.orm = useService("orm")
        //this.currentOrder = this.pos.get_order();
        //this.poss = usePos();
        _superSetup.apply(this, arguments);
    },

    async onClickTicketExchange() {
        const destinationOrder = this.pos.get_order();
        if (destinationOrder) {
            try {
                const ondoInventory =  await this.move_to_inventory();

                if (!ondoInventory){
                    this.pos.toRefundLines = {}
                    return;
                }

                this.pos.set_order(destinationOrder);
                const partner = this.getSelectedPartner();       
                const refundDetails = this._getRefundableDetails(partner);
                const taxById = Object.fromEntries(this.pos.taxes.map(t => [t.id, t]));
                const includeTax = this.pos.config.iface_tax_included;

                let totalRefund = refundDetails.reduce((sum, detail) => {
                  const netPrice = detail.orderline.price / 1.16 ;    // sin impuestos
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

                 //crea una lines de cambio en la tabla de cambios.
                const origin_id = refundDetails.map(d => d.orderline.orderBackendId);
                const productId_origin =  refundDetails.map(d => d.orderline.productId);
                await this.orm.call(
                'pos.changes',
                'poschanges_links_pre',
                [
                  origin_id,
                  destinationOrder.uid,
                  productId_origin
                ]
                );
                
                await ProductScreen.prototype._applyCoupon.call(this, totalRefund);
                this.pos.showScreen("ProductScreen");
                this.pos.toRefundLines = {};            
               
                //const couponId = await this.createCoupon(destinationOrder,totalRefund);
        } catch (error) {
            this.pos.toRefundLines = {};
            alert("Error al guardar reembolso: " + (error.message || "Hubo un error al guardar la orden de reembolso."));
        }
      }
    },
   

    async move_to_inventory(order, totalRefund) {
      //const partner = this.getSelectedPartner();
      const details = Object.values(this.pos.toRefundLines);
      const refundDetails =  details.filter(d => d.qty > 0).map(d => d.orderline);
      const detallesArray = Object.values(refundDetails);

      if (!detallesArray.length) {
          return alert("selecciona un articulo")
      }

      const backendId = detallesArray[0].orderBackendId;
      console.log('backendId',backendId)
      const selectRefundProductId = detallesArray.map(detail => ({
          productId:      detail.productId,
      }));

      const refundIds = selectRefundProductId.map(o => o.productId);
      const res = await this.orm.call(
          "pos.order",
          "get_order_locations",
          [[backendId]]
      );


      const locations = res[backendId] || [];
      const filteredLocations = locations.filter(loc =>
        refundIds.includes(loc.product_id)
      );
      console.log("refundIds",refundIds)
      
      const firstLoc = locations[0];

      console.log("firstLoc",firstLoc);
      if (!firstLoc) {
          alert("No hay movimiento de salida en este articulo, ")
          return false
      }

      // 5) Por cada línea, creo el picking de entrada
      for (const detail of detallesArray) {
          const productId = detail.productId;
          const qty = detail.qty;
          const newQty = qty; //*-1;

          // //5.0 Actualizo cada orderline en negativo
          const lineIds = await this.orm.call(
            'pos.order.line',     // modelo (string)
            'search',             // método (string)
            [[                    // args: array con tu dominio
              ['order_id',   '=', backendId],
              ['product_id', '=', productId],
            ]],
            {}                    // kwargs (objeto)
          );

          await this.orm.call(
            'pos.order.line',
            'write',
            [ lineIds, { changes: newQty } ],
            {}
          );

          // 5.1) UoM del producto
          const [prod] = await this.orm.call(
              "product.product",    // modelo
              "read",               // método
              [[productId], ["uom_id"]],
              {}
          );
          const uomId = prod.uom_id[0];

          // 5.2) Tipo de operación “incoming” para tu compañía
          const [pt] = await this.orm.call(
            "stock.picking.type",                    // modelo
            "search_read",                           // método
            [
              [
                ["code", "=", "incoming"],
                ["warehouse_id.company_id", "=", this.pos.company.id],
              ],
            ],                                        // args: [ [ domain tuples ] ]
            { fields: ["id"] }                       // kwargs
          );
          if (!pt) {
            console.log("pt",pt)
              alert("No existe un tipo de operación de entrada configurado.......");
              return false
          }

          // 5.3) Crear el picking
          const pickingVals = {
              origin: `POS Return ${backendId}`,
              picking_type_id: pt.id,
              location_id: firstLoc.origin_id,
              location_dest_id: firstLoc.location_id,
          move_ids_without_package: [
          [0, 0, {
              product_id: productId,
              product_uom_qty: qty,
              product_uom: uomId,
              name: "Devolución POS",
              location_id: firstLoc.origin_id ,
              location_dest_id: firstLoc.location_id,
              }],
          ],
          };

          const pickingId = await this.orm.call(
              "stock.picking",       // modelo
              "create",              // método
              [pickingVals],         // args
              {}                     // kwargs
          );

          // 5.4) Confirmar, reservar y validar
          await this.orm.call("stock.picking", "action_confirm",    [[pickingId]]);
          await this.orm.call("stock.picking", "action_assign",     [[pickingId]]);
          await this.orm.call("stock.picking", "button_validate",   [[pickingId]]);

          return true
      }
    },
});

