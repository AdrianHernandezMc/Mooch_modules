/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService, useBus } from "@web/core/utils/hooks";
import { Component, onWillStart, useState

 } from "@odoo/owl";



//alert("entro")
class ExchangeList extends Component {
    setup() {
      super.setup(...arguments);

        this.state = useState({
          data_changes: [],
          items: 0,
        })
        this.orm = useService("orm");

        onWillStart(async() => {
          await this.loadChanges()
        })
        this.model = 'pos.changes';
      }

      async loadChanges(){
        const domain= [];
        const field_list = ['id', 'dest_order_uid']
        this.state.data_changes = await this.orm.searchRead(
          this.model,
          domain,
          field_list
        ) 
        console.log("changes",this.state.data_changes)
      }

  static template = "exchange.exchanges_template";
}

// Clave EXACTA que aparece en el XML
registry.category("actions").add("exchage_changes_componet",ExchangeList);
alert("Registro");



