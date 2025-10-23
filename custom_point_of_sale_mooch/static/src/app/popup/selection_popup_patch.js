/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { useService } from "@web/core/utils/hooks";
import { PasswordInputPopup } from "@custom_point_of_sale_mooch/app/popup/hide_passwordpopup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

patch(SelectionPopup.prototype, {
    setup() {
        super.setup(...arguments);
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.posService = useService("pos");
        
        // Filtrar lista inicial para mostrar solo NO administradores
        if (this.props.title && this.props.title.includes('cajero')) {
            this.filterInitialList();
        }
    },

    /**
     * Filtra la lista inicial de empleados para mostrar únicamente
     * aquellos que no tienen permisos avanzados en la configuración del POS.
     */
    filterInitialList() {
        const config = this.posService.config;
        const allEmployees = this.posService.employees || [];
        
        if (!config || !config.advanced_employee_ids || !Array.isArray(config.advanced_employee_ids)) {
            return;
        }

        // Extraer IDs de empleados avanzados desde la configuración
        let advancedEmployeeIds = [];
        if (Array.isArray(config.advanced_employee_ids) && config.advanced_employee_ids.length > 0) {
            if (typeof config.advanced_employee_ids[0] === 'object') {
                advancedEmployeeIds = config.advanced_employee_ids.map(emp => 
                    emp && emp.id ? emp.id : (emp && emp[0] ? emp[0] : null)
                ).filter(id => id !== null);
            } else if (Array.isArray(config.advanced_employee_ids[0])) {
                advancedEmployeeIds = config.advanced_employee_ids.map(emp => emp[0]).filter(id => id !== undefined);
            } else {
                advancedEmployeeIds = config.advanced_employee_ids.filter(id => id !== undefined);
            }
        }

        // Filtrar empleados no administradores
        const nonAdminEmployees = allEmployees.filter(employee => 
            !advancedEmployeeIds.includes(employee.id)
        );

        // Formatear lista según lo que espera SelectionPopup
        const formattedNonAdminList = nonAdminEmployees.map(employee => ({
            id: employee.id,
            label: employee.name || `Empleado ${employee.id}`,
            item: employee,
            toString() {
                return this.label;
            },
        }));

        // Reemplazar la lista original con la lista filtrada
        if (formattedNonAdminList.length > 0) {
            this.props.list = formattedNonAdminList;
        }
    },

    /**
     * Muestra los empleados administradores tras validar el NIP de acceso.
     * Si el NIP es correcto, se abre un nuevo SelectionPopup con los administradores.
     */
    async showAdvancedEmployees() {
        // 1) Solicitar NIP al usuario
        const { confirmed, payload } = await this.popup.add(PasswordInputPopup, {
            title: "Acceso a Administradores",
            body: "Ingresa la contraseña para acceder a empleados avanzados:",
            confirmText: "Validar",
            cancelText: "Cancelar",
        });
        if (!confirmed || !payload) return;

        const nip = String(payload).trim();

        try {
            // 2) Validar NIP en el backend
            const validation = await this.orm.call("hr.employee", "check_pos_nip", [nip], {});
            if (!validation?.ok) {
                await this.popup.add(ErrorPopup, {
                    title: "Contraseña Incorrecta",
                    body: "La contraseña ingresada no es válida.",
                });
                return;
            }

            // 3) Construir lista de empleados administradores
            const config = this.posService.config;
            const allEmployees = this.posService.employees || [];

            let advancedEmployeeIds = [];
            if (Array.isArray(config?.advanced_employee_ids) && config.advanced_employee_ids.length > 0) {
                if (typeof config.advanced_employee_ids[0] === "object") {
                    advancedEmployeeIds = config.advanced_employee_ids
                        .map((emp) => (emp?.id ? emp.id : emp?.[0] ?? null))
                        .filter((id) => id !== null);
                } else if (Array.isArray(config.advanced_employee_ids[0])) {
                    advancedEmployeeIds = config.advanced_employee_ids
                        .map((emp) => emp[0])
                        .filter((id) => id !== undefined);
                } else {
                    advancedEmployeeIds = config.advanced_employee_ids.filter((id) => id !== undefined);
                }
            }

            const advancedEmployees = allEmployees.filter((e) => advancedEmployeeIds.includes(e.id));
            if (!advancedEmployees.length) {
                await this.popup.add(ErrorPopup, {
                    title: "Sin Administradores",
                    body: "No hay administradores configurados en el sistema.",
                });
                return;
            }

            // 4) Mostrar nuevo popup con la lista de administradores
            const adminListForPopup = advancedEmployees.map((employee) => ({
                id: employee.id,
                label: employee.name || `Empleado ${employee.id}`,
                item: employee,
                toString() { return this.label; },
            }));

            const { confirmed: employeeConfirmed, payload: selectedEmployee } = await this.popup.add(SelectionPopup, {
                title: "Seleccionar Administrador",
                list: adminListForPopup,
                confirmText: "Seleccionar",
                cancelText: "Cancelar",
            });

            // 5) Si confirman, resolver el popup original con el empleado elegido
            if (employeeConfirmed && selectedEmployee) {
                this.props.resolve({ confirmed: true, payload: selectedEmployee });
                this.props.close();
            }

        } catch (error) {
            await this.popup.add(ErrorPopup, {
                title: "Error de Validación",
                body: "No se pudo validar la contraseña. Intenta nuevamente.",
            });
        }
    },
});
