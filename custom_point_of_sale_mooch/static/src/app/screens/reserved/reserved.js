/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ApartadosPopup extends Component {
    static template = "point_of_sale.ApartadosPopup";
    
    setup() {
        this.pos = useService("pos");
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.state = useState({
            apartados: [],
            apartadoSeleccionado: null,
            cargando: false
        });
        // Cargar apartados al abrir
        this.cargarApartados();
    }

    closePopup() {
        if (this.props.close) this.props.close();
    }

    // Cargar apartados desde la base de datos
    async cargarApartados() {
        this.state.cargando = true;
            const apartados = await this.orm.call(
                "pos.reserved",
                "search_read",
                [],
                {
                    fields: ["name", "state", "amount_total", "amount_paid", "cashier"],
                    order: "id desc"
                }
            );
            
            // Cargar líneas para cada apartado
           for (let apartado of apartados) {
                const lineas = await this.orm.call(
                    "pos.reserved.line",
                    "search_read",
                    [[["reserved_id", "=", apartado.id]]],  // 🔵 lista de listas
                    {
                        fields: ["product_id", "name", "qty", "price_unit", "price_subtotal_incl"]
                    }
                );
                apartado.lineas = lineas || [];
            }
            this.state.apartados = apartados;
            this.state.cargando = false;
    }

    // Seleccionar un apartado
    seleccionarApartado(apartado) {
        this.state.apartadoSeleccionado = apartado;
    }

    // Cargar apartado al POS actual
    cargarAlPOS() {
        if (!this.state.apartadoSeleccionado) {
            this.notification.add("Selecciona un apartado primero", {type: "warning"});
            return;
        }

        const apartado = this.state.apartadoSeleccionado;
        
        // Limpiar orden actual
        this.pos.orders[0].orderlines.removeAll();
        
        // Agregar productos del apartado al POS
        apartado.lineas.forEach(linea => {
            const producto = this.pos.db.get_product_by_id(linea.product_id[0]);
            if (producto) {
                this.pos.orders[0].add_product(producto, {
                    quantity: linea.qty,
                    price: linea.price_unit,
                    extras: {
                        price_manually_set: true
                    }
                });
            }
        });

        this.notification.add(`Apartado ${apartado.name} cargado al POS`, {type: "success"});
        this.props.close();
    }

    // Crear nuevo apartado desde la orden actual
    async crearApartado() {
        const ordenActual = this.pos.get_order();
        if (!ordenActual || ordenActual.orderlines.length === 0) {
            this.notification.add("No hay productos en la orden actual", {type: "warning"});
            return;
        }

        this.state.cargando = true;
        //try {
            // Crear el apartado
            console.log("crearapartados")
            const apartadoId = await this.orm.call(
                "pos.reserved",
                "create",
                [{
                    name: `APARTADO-${new Date().getTime()}`,
                    state: "reserved",
                    amount_total: ordenActual.get_total_with_tax(),
                    amount_paid: 0,
                    cashier: this.pos.get_cashier().name,
                    note: "Creado desde POS"
                }]
            );

            // Crear líneas del apartado
            for (let linea of ordenActual.orderlines) {
                await this.orm.call(
                    "pos.reserved.line",
                    "create",
                    [{
                        reserved_id: apartadoId,
                        product_id: linea.product.id,
                        name: linea.product.display_name,
                        qty: linea.quantity,
                        price_unit: linea.price,
                        price_subtotal_incl: linea.price * linea.quantity
                    }]
                );
            }

            this.notification.add("Apartado creado correctamente", {type: "success"});
            this.cargarApartados(); // Recargar lista
        // } catch (error) {
        //     this.notification.add("Error creando apartado: " + error, {type: "danger"});
        // } finally {
            this.state.cargando = false;
        //}
    }

    // Eliminar apartado
    async eliminarApartado() {
        if (!this.state.apartadoSeleccionado) {
            this.notification.add("Selecciona un apartado primero", {type: "warning"});
            return;
        }

        if (!confirm("¿Estás seguro de eliminar este apartado?")) {
            return;
        }

        try {
            await this.orm.call(
                "pos.reserverd",
                "unlink",
                [[this.state.apartadoSeleccionado.id]]
            );
            
            this.notification.add("Apartado eliminado", {type: "success"});
            this.state.apartadoSeleccionado = null;
            this.cargarApartados(); // Recargar lista
        } catch (error) {
            this.notification.add("Error eliminando apartado: " + error, {type: "danger"});
        }
    }
}
//registry.category("popups").add("ApartadosPopup", ApartadosPopup);