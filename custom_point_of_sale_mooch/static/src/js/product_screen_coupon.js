/** @odoo-module **/
import { patch }                 from '@web/core/utils/patch';
import { ProductScreen }         from '@point_of_sale/app/screens/product_screen/product_screen';
import { useService }            from '@web/core/utils/hooks';


const _superSetup = ProductScreen.prototype.setup;


patch(ProductScreen.prototype, {
  setup() {
    this.pos = useService('pos');
    _superSetup.apply(this, arguments);
  },

  async _applyCoupon(code, totalRefund) {
    // //try {
      //alert("Entro")
      const order = this.pos.get_order();
      //console.log("order",order)
      const product = this.pos.db.get_product_by_id(401);
    
      try {
         order.add_product(product, {
              quantity: 1,
              price:    -totalRefund,
              merge:    false,
              uom_id:   [1, 'Unidad']
         });
         

      // 2) Invocamos el método parcheado en Order.prototype
      //alert("Llego a activate code")
//      const result = await order._activateCode(code);
     // alert(`${result} – ${code}`);
     // console.log("resultado",result);

      } catch (error) {
        return alert(error.message || 'Error al activar el cupón');
      }

      this.pos.showScreen('TicketScreen');
      //alert("aplico todo");
      //  const lineToRemove = order.get_orderlines().find(line => line.get_product().id === 123);


      //this.pos.showScreen("ProductScreen")


       //
      // if (lineToRemove) {
      //     order.removeOrderline(lineToRemove);
      //   }
      //const order = this.pos.get_order();
        //console.log(payload.coupon_id)
       //order.set_coupon_id?.(payload.coupon_id);
      //

  }
});





    // async _activateCode(code, partner) {
    //     alert("_activateCode");
    //     console.log('POS Store:', this.pos);
    //
    //     const rules = this.pos.rules || [];
    //      console.log('Promotional rules loaded:', rules);
    //       console.log('Reglas cargadas:', rules);
    //
    //       const rule = rules.find(r =>
    //         r.mode === 'with_code' &&
    //         (r.code   === code || r.barcode === code)
    //       );
    //
    //
    //    //  console.log(this.pos.rules);
    //    //  console.log("hola");
    //    //  // 1) Intentar encontrar una regla de promoción
    //    // const rule = this.pos.rules.find((rule) => {
    //    //      return rule.mode === "with_code" && (rule.promo_barcode === code || rule.code === code);
    //    //  });
    //     alert("Rule");
    //     // Esto es solo la rama de cupones (no reglas)
    //     // if (!rule) {
    //     //     // Prepara los argumentos para use_coupon_code
    //     //     const order   = this.env.pos.get_order();
    //     //     const configId = this.env.pos.config.id;
    //     //     const partner  = order.get_client();
    //     //     const partnerId = partner ? partner.id : false;
    //     //     const pricelistId = this.env.pos.pricelist.id;
    //     //     const creationDate = new Date().toISOString();
    //     //
    //     //     const args = [
    //     //         [configId],         // IDs de pos.config
    //     //         code,               // código ingresado
    //     //         creationDate,       // timestamp ISO
    //     //         partnerId,          // ID de cliente o false
    //     //         pricelistId         // ID de tarifario
    //     //     ];
    //     //
    //     //     // Llamada al backend
    //     //     const { successful, payload } = await this.orm.call(
    //     //         'pos.config',
    //     //         'use_coupon_code',
    //     //         args
    //     //     );
    //     //
    //     //     // Manejo de fallo
    //     //     if (!successful) {
    //     //         this.popup.add(ErrorPopup, {
    //     //             title: 'Error',
    //     //             body:  payload.error_message,
    //     //         });
    //     //         return false;
    //     //     }
    //     //
    //     //     // 2) Aplica línea de cupón si viene
    //     //     if (payload.coupon_id) {
    //     //         const prod = this.pos.db.get_product_by_id(payload.coupon_id);
    //     //         if (prod) {
    //     //             order.add_product(prod, { quantity: 1 });
    //     //         }
    //     //     }
    //     //
    //     //     // 3) Aplica descuento basado en puntos si hay
    //     //     if (payload.points) {
    //     //         order.set_discount(payload.points);
    //     //     }
    //     //
    //     //     // 4) Vuelve a ProductScreen para que se vea el cambio
    //     //     this.chrome.showScreen('ProductScreen');
    //     //     return true;
    //     //}
    //
    //     // … aquí iría la lógica completa para reglas de promoción …
    //     return false;
    // },

//});



  // async onApplyCouponClick() {
    //     const order = this.pos.get_order();
    //     alert(order.name);
    //     this.couponCode= '044f-cb5e-446f'
    //
    //     // if (!order) {
    //     //     await this.popup.showPopup('ErrorPopup', {
    //     //       title: 'Error',
    //     //       body:  'No hay orden activa.',
    //     //     });
    //     // }
    //     try {
    //         // Mensaje de error si el cupón no es válido o expiró :contentReference[oaicite:0]{index=0}
    //         const configId      = this.pos.config.id;          // ID único de pos.config
    //         const couponCode    = this.couponCode;                 // tu código de cupón (string)
    //         const creationDate  = new Date().toISOString();        // timestamp ISO, p.ej. "2025-07-16T15:00:00.000Z"
    //         const isRefund      = false;                           // o true si viene de un reembolso
    //         const validateLoyalty = false;                         // o true si quieres validar/usar puntos
    //
    //         const args = [
    //               [configId],          // lista de IDs de pos.config que invocan el método
    //               couponCode,          // el cupón introducido
    //               creationDate,        // fecha de creación en ISO
    //               isRefund,            // flag refund
    //               validateLoyalty      // flag loyalty
    //         ];
    //
    //         const result = await this.orm.call(
    //           'pos.config',        // modelo
    //           'use_coupon_code',   // método Python
    //           args,                // args tal como arriba
    //         );
    //
    //         const { successful, payload } = result;
    //
    //
    //         if (!successful) {
    //             this.popup.add(ErrorPopup, {
    //                 title: 'Error',
    //                 body:  'No se pudo aplicar el cupón.',
    //             });
    //         }
    //
    //         // 3) Ahora payload tiene tus datos:
    //         const {
    //             program_id,
    //             coupon_id,
    //             coupon_partner_id,
    //             points,
    //             has_source_order
    //         } = payload;
    //
    //         // Mostrar en un alert (solo de ejemplo)
    //         alert(`Cupón aplicado:\n· Programa: ${program_id}\n· ID cupón: ${coupon_id}\n· Puntos: ${points}`);
    //
    //         // 4) Si quieres tratar 'points' como descuento, haz:
    //         if (points) {
    //             alert(`points: ${points}`)
    //             // por ejemplo, porcentaje:
    //             //order.set_discount(points);
    //             alert(`cupon_id: ${coupon_id}`)
    //             // o como monto fijo:
    //             order.set_global_discount_amount(points);
    //         }
    //
    //         // 5) Si quisieras añadir un producto “cupón”:
    //         alert(`cupon_id: ${coupon_id}`)
    //         if (coupon_id) {
    //             alert(`cupon_id: ${coupon_id}`)
    //             const prod = this.env.pos.db.get_product_by_id(coupon_id);
    //             if (prod) {
    //                 order.add_product(prod, { quantity: 1 });
    //             }
    //         }
    //
    //         // 6) Finalmente, OWL re-renderiza automáticamente
    //         //    (si vienes de otra pantalla, podrías volver así:)
    //         this.pos.showScreen('ProductScreen');
    //
    //
    //     } catch (e) {
    //         console.error('Error al aplicar cupón:', e);
    //         // await this.popup.showPopup('ErrorPopup', {
    //         //     title: 'Error de conexión',
    //         //     body: e.message,
    //         //     });
    //     }
    // },