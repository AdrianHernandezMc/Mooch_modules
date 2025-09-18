/** @odoo-module **/
import { patch }                 from '@web/core/utils/patch';
import { ProductScreen }         from '@point_of_sale/app/screens/product_screen/product_screen';
import { useService }            from '@web/core/utils/hooks';

const _superSetup = ProductScreen.prototype.setup;

patch(ProductScreen.prototype, {
  setup() {
    this.pos = useService('pos');
    this.orm = useService("orm");
    this.cfgId = null;
    _superSetup.apply(this, arguments);
  },

  async _applyCoupon(totalRefund, ordername) {
    const order = this.pos.get_order();
    //alert("Agrega producto a product_screen")
    const cfgId = this.pos.config.id;
    const pid = await this.orm.call("pos.config", "get_changes_product_id", [cfgId], {});

    this.changesProductId = pid || null;

    let product = this.pos.db.get_product_by_id(pid);
    product.display_name = product.display_name + " ord: " + ordername
    
    try {
      order.add_product(product, {
          quantity: 1,
          price:    -totalRefund,
          merge:    false,
          uom_id:   [1, 'Unidad']
    });

    } catch (error) {
      return alert(error.message || 'Error al activar el cupón');
    }
    this.pos.showScreen('TicketScreen');
  }
});