/** @odoo-module **/
import { useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

export class SelectionPopupPay extends AbstractAwaitablePopup {
  //static template = 'exchange_buttons.SelectionPopup';

  setup() {
    super.setup();
    // Valor inicial: el primero de la lista, o null si no hay ninguno
    this.state = useState({
      currentValue: this.props.list.length ? this.props.list[0].id : null,
    });
  }
  selectItem(id) {
    this.state.currentValue = id;
  }
  getPayload() {
    return this.state.currentValue;
  }
}
SelectionPopupPay.template = "exchange_buttons.SelectionPopup";

// registry
//   .category('point_of_sale.popups')
//   .add('SelectionPopupPay', SelectionPopupPay);
