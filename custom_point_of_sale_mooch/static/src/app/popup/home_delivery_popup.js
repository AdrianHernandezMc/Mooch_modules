/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

export class HomeDeliveryPopup extends Component {
    static template = "custom_point_of_sale_mooch.HomeDeliveryPopup";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        // ✅ CORREGIDO: Usar el servicio correcto para popups
        this.popup = useService("popup"); 
        
        const order = this.props.order;
        const partner = order?.get_partner?.() || {};

        console.log("🔍 DEBUG - Campos del partner en POS:", Object.keys(partner).sort());

        // ✅ ESTADO INICIAL VACÍO - se llenará con RPC
        this.state = useState({
            // Datos de contacto (iniciales desde POS)
            contact_name: partner.name || "",
            phone: partner.phone || partner.mobile || "",
            address: this.getPartnerFullAddress(partner) || "",
            notes: "",

            // Coordenadas (vacías inicialmente)
            lat: "",
            lng: "",
            maps_url: "",

            // Estados
            map_loaded: false,
            searching_address: false,
            reverse_geocoding: false,
            getting_location: true,
            loading_partner_data: true, // ✅ Nuevo estado
            partner_data_loaded: false
        });

        this.map = null;
        this.marker = null;
        this.autocomplete = null;
        this.geocoder = null;

        onMounted(async () => {
            // ✅ PRIMERO cargar datos delivery del partner
            await this.loadPartnerDeliveryData(partner);
            // ✅ LUEGO inicializar ubicación
            this.getInitialLocation();
        });

        onWillUnmount(() => {
            this.cleanup();
        });
    }

    // ✅ NUEVO MÉTODO: Cargar datos delivery del partner via RPC
    async loadPartnerDeliveryData(partner) {
        if (!partner?.id) {
            console.log("❌ No hay partner ID");
            this.state.loading_partner_data = false;
            return;
        }

        try {
            console.log("🔄 Cargando datos delivery del partner ID:", partner.id);
            
            const partnerData = await this.orm.read(
                "res.partner", 
                [partner.id], 
                [
                    'delivery_contact_name', 'delivery_phone', 'delivery_address',
                    'delivery_notes', 'delivery_lat', 'delivery_lng', 'delivery_maps_url',
                    'street', 'street2', 'city', 'state_id', 'country_id', 'zip'
                ]
            );

            if (partnerData && partnerData[0]) {
                const data = partnerData[0];
                console.log("✅ Datos delivery cargados via RPC:", data);
                
                // ✅ ACTUALIZAR ESTADO con datos del partner
                if (data.delivery_contact_name) {
                    this.state.contact_name = data.delivery_contact_name;
                }
                if (data.delivery_phone) {
                    this.state.phone = data.delivery_phone;
                }
                if (data.delivery_address) {
                    this.state.address = data.delivery_address;
                }
                if (data.delivery_notes) {
                    this.state.notes = data.delivery_notes;
                }
                if (data.delivery_lat) {
                    this.state.lat = data.delivery_lat.toString();
                }
                if (data.delivery_lng) {
                    this.state.lng = data.delivery_lng.toString();
                }
                if (data.delivery_maps_url) {
                    this.state.maps_url = data.delivery_maps_url;
                }

                this.state.partner_data_loaded = true;
                console.log("✅ Estado actualizado con datos delivery:", {
                    contact_name: this.state.contact_name,
                    phone: this.state.phone,
                    address: this.state.address,
                    lat: this.state.lat,
                    lng: this.state.lng
                });
            } else {
                console.log("ℹ️ Partner no tiene datos delivery guardados");
            }
        } catch (error) {
            console.error("❌ Error cargando datos delivery:", error);
        } finally {
            this.state.loading_partner_data = false;
        }
    }

    getPartnerFullAddress(partner) {
        if (!partner) return "";

        const addressParts = [
            partner.street,
            partner.street2,
            partner.city,
            partner.state_id ? (Array.isArray(partner.state_id) ? partner.state_id[1] : "") : "",
            partner.country_id ? (Array.isArray(partner.country_id) ? partner.country_id[1] : "") : "",
            partner.zip
        ].filter(part => part && part.toString().trim());

        return addressParts.join(', ');
    }

    cleanup() {
        if (this.map) {
            google.maps.event.clearInstanceListeners(this.map);
        }
        if (this.marker) {
            google.maps.event.clearInstanceListeners(this.marker);
        }
        if (this.autocomplete) {
            google.maps.event.clearInstanceListeners(this.autocomplete);
        }

        // Remover event listener del input
        const input = document.getElementById('address-input');
        if (input) {
            const newInput = input.cloneNode(true);
            input.parentNode.replaceChild(newInput, input);
        }
    }

    // NUEVA FUNCIÓN: Obtener ubicación inicial - CORREGIDA
    getInitialLocation() {
        console.log("🔍 getInitialLocation() - Estado:", {
            lat: this.state.lat,
            lng: this.state.lng,
            loading: this.state.loading_partner_data
        });

        // ✅ ESPERAR a que terminen de cargar los datos del partner
        if (this.state.loading_partner_data) {
            console.log("⏳ Esperando carga de datos del partner...");
            setTimeout(() => this.getInitialLocation(), 100);
            return;
        }

        // ✅ PRIMERO: Si ya tenemos coordenadas válidas del PARTNER, USARLAS
        if (this.state.lat && this.state.lng && 
            parseFloat(this.state.lat) !== 0.0 && 
            parseFloat(this.state.lng) !== 0.0) {
            console.log("✅ Usando coordenadas del PARTNER:", this.state.lat, this.state.lng);
            this.state.getting_location = false;
            this.loadGoogleMaps();
            return;
        }

        console.log("🔄 No hay coordenadas del partner, obteniendo ubicación actual...");

        // ✅ SEGUNDO: Solo obtener ubicación actual si NO hay coordenadas existentes
        if (!navigator.geolocation) {
            console.warn("Geolocation not supported, using default location");
            this.state.getting_location = false;
            this.loadGoogleMaps();
            return;
        }

        console.log("🔄 Obteniendo ubicación actual (no hay coordenadas existentes)");
        this.state.getting_location = true;

        navigator.geolocation.getCurrentPosition(
            (pos) => {
                console.log("📍 Ubicación actual obtenida:", pos.coords.latitude, pos.coords.longitude);
                this.state.lat = pos.coords.latitude.toFixed(6);
                this.state.lng = pos.coords.longitude.toFixed(6);
                this.state.maps_url = `https://maps.google.com/?q=${this.state.lat},${this.state.lng}`;
                this.state.getting_location = false;
                
                // Obtener dirección de la ubicación actual
                if (window.google && window.google.maps) {
                    this.getAddressFromCoordinates(pos.coords.latitude, pos.coords.longitude);
                }
                
                this.loadGoogleMaps();
            },
            (err) => {
                console.warn("❌ No se pudo obtener ubicación actual:", err);
                // Solo usar ubicación por defecto si NO hay coordenadas existentes
                if (!this.state.lat || !this.state.lng) {
                    this.state.lat = "20.659698";
                    this.state.lng = "-103.349609";
                    console.log("📍 Usando ubicación por defecto");
                }
                this.state.getting_location = false;
                this.loadGoogleMaps();
            },
            { 
                enableHighAccuracy: false,
                timeout: 10000, 
                maximumAge: 60000 
            }
        );
    }

    async loadGoogleMaps() {
        // Verificar si ya está cargado
        if (window.google && window.google.maps) {
            this.state.map_loaded = true;
            setTimeout(() => this.initMap(), 100);
            return;
        }

        // Verificar si hay API key
        if (!this.props.config?.google_maps_api_key) {
            console.warn("No Google Maps API key configured");
            this.state.map_loaded = true;
            return;
        }

        try {
            // Cargar Google Maps CON la librería places
            await new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = `https://maps.googleapis.com/maps/api/js?key=${this.props.config.google_maps_api_key}&libraries=places`;
                script.async = true;
                script.defer = true;
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            });

            this.state.map_loaded = true;
            setTimeout(() => this.initMap(), 500);
        } catch (error) {
            console.error("Error loading Google Maps:", error);
            this.state.map_loaded = true;
        }
    }

    initMap() {
        if (!this.state.map_loaded || !window.google || !window.google.maps) {
            console.warn("Google Maps not available");
            return;
        }

        try {
            // Usar las coordenadas actuales (ya sea ubicación real o por defecto)
            const currentLat = parseFloat(this.state.lat) || 20.659698;
            const currentLng = parseFloat(this.state.lng) || -103.349609;
            const currentLocation = new google.maps.LatLng(currentLat, currentLng);

            // Crear mapa CON iconos habilitados
            this.map = new google.maps.Map(document.getElementById('delivery-map'), {
                center: currentLocation,
                zoom: 15,
                mapTypeControl: true,
                streetViewControl: true,
                fullscreenControl: true,
                styles: [
                    {
                        "featureType": "administrative",
                        "elementType": "labels.text.fill",
                        "stylers": [{"color": "#444444"}]
                    },
                    {
                        "featureType": "landscape",
                        "elementType": "all",
                        "stylers": [{"color": "#f2f2f2"}]
                    },
                    {
                        "featureType": "poi", // Puntos de interés - AHORA VISIBLES
                        "elementType": "all",
                        "stylers": [{"visibility": "on"}] // Cambiado de "off" a "on"
                    },
                    {
                        "featureType": "poi.business", // Negocios
                        "elementType": "all",
                        "stylers": [{"visibility": "on"}]
                    },
                    {
                        "featureType": "poi.medical", // Hospitales, farmacias
                        "elementType": "all",
                        "stylers": [{"visibility": "on"}]
                    },
                    {
                        "featureType": "poi.school", // Escuelas
                        "elementType": "all",
                        "stylers": [{"visibility": "on"}]
                    },
                    {
                        "featureType": "poi.sports_complex", // Complejos deportivos
                        "elementType": "all",
                        "stylers": [{"visibility": "on"}]
                    },
                    {
                        "featureType": "road",
                        "elementType": "all",
                        "stylers": [{"saturation": -100}, {"lightness": 45}]
                    },
                    {
                        "featureType": "road.highway",
                        "elementType": "all",
                        "stylers": [{"visibility": "simplified"}]
                    },
                    {
                        "featureType": "road.arterial",
                        "elementType": "labels.icon",
                        "stylers": [{"visibility": "off"}]
                    },
                    {
                        "featureType": "transit", // Transporte público
                        "elementType": "all",
                        "stylers": [{"visibility": "on"}] // Cambiado de "off" a "on"
                    },
                    {
                        "featureType": "water",
                        "elementType": "all",
                        "stylers": [{"color": "#4c6b8a"}, {"visibility": "on"}]
                    }
                ]
            });

            // Crear marcador
            this.marker = new google.maps.Marker({
                map: this.map,
                position: currentLocation,
                title: "Ubicación de entrega",
                draggable: true,
                animation: google.maps.Animation.DROP
            });

            // Inicializar geocoder y autocomplete
            this.geocoder = new google.maps.Geocoder();
            this.initAutocomplete();

            // Configurar eventos del mapa
            this.setupMapEvents();

            // Si ya hay coordenadas, actualizar la dirección
            if (this.state.lat && this.state.lng) {
                this.getAddressFromCoordinates(currentLat, currentLng);
            }

            console.log("Mapa inicializado con ubicación del partner");

        } catch (error) {
            console.error("Error initializing map:", error);
        }
    }

    initAutocomplete() {
        if (!window.google.maps.places) {
            console.warn("Google Maps Places library not loaded");
            return;
        }

        try {
            const input = document.getElementById('address-input');
            if (!input) {
                console.warn("Address input not found");
                return;
            }

            // Crear autocompletado
            this.autocomplete = new google.maps.places.Autocomplete(input, {
                types: ['address'],
                componentRestrictions: { country: 'mx' }, // Restringir a México
                fields: ['formatted_address', 'geometry', 'name']
            });

            // Cuando se selecciona una dirección del autocomplete
            this.autocomplete.addListener('place_changed', () => {
                const place = this.autocomplete.getPlace();
                
                if (!place.geometry) {
                    console.warn("No se pudo obtener la ubicación para: '" + place.name + "'");
                    return;
                }

                // Centrar mapa en la ubicación seleccionada
                this.map.setCenter(place.geometry.location);
                this.map.setZoom(17);
                
                // Mover marcador
                this.marker.setPosition(place.geometry.location);
                
                // Actualizar coordenadas y dirección
                this.updateLocationFromMap(place.geometry.location);
                
                // Si el lugar tiene dirección, actualizarla
                if (place.formatted_address) {
                    this.state.address = place.formatted_address;
                }
            });

            // Prevenir envío del formulario al presionar Enter
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    
                    // Si hay texto en el input, buscar esa dirección
                    if (input.value.trim()) {
                        this.searchAddressDirectly(input.value);
                    }
                }
            });

        } catch (error) {
            console.error("Error initializing autocomplete:", error);
        }
    }

    setupMapEvents() {
        // Evento cuando se mueve el marcador
        google.maps.event.addListener(this.marker, 'dragend', () => {
            const position = this.marker.getPosition();
            this.updateLocationFromMap(position);
        });

        // Evento cuando se hace clic en el mapa
        google.maps.event.addListener(this.map, 'click', (event) => {
            this.marker.setPosition(event.latLng);
            this.updateLocationFromMap(event.latLng);
        });
    }

    updateLocationFromMap(latLng) {
        if (!latLng) return;

        try {
            this.state.lat = latLng.lat().toFixed(6);
            this.state.lng = latLng.lng().toFixed(6);
            this.state.maps_url = `https://maps.google.com/?q=${this.state.lat},${this.state.lng}`;
            
            // Obtener dirección desde coordenadas
            this.getAddressFromCoordinates(latLng.lat(), latLng.lng());
        } catch (error) {
            console.error("Error updating location from map:", error);
        }
    }

    getAddressFromCoordinates(lat, lng) {
        if (!window.google.maps.Geocoder) return;

        this.state.reverse_geocoding = true;

        try {
            const geocoder = new google.maps.Geocoder();
            const location = new google.maps.LatLng(lat, lng);
            
            geocoder.geocode({ location: location }, (results, status) => {
                this.state.reverse_geocoding = false;
                
                if (status === 'OK' && results[0]) {
                    this.state.address = results[0].formatted_address;
                } else {
                    console.warn("No se pudo obtener la dirección para las coordenadas:", lat, lng);
                    this.state.address = "Dirección no disponible - usa el buscador de direcciones";
                }
            });
        } catch (error) {
            this.state.reverse_geocoding = false;
            console.error("Error in geocoding:", error);
        }
    }

    searchAddressDirectly(address) {
        if (!this.geocoder || !address.trim()) return;

        this.state.searching_address = true;

        this.geocoder.geocode({ 
            address: address + ', Tlajomulco de Zúñiga, Jalisco' 
        }, (results, status) => {
            this.state.searching_address = false;
            
            if (status === 'OK' && results[0]) {
                const location = results[0].geometry.location;
                
                // Centrar mapa
                this.map.setCenter(location);
                this.map.setZoom(16);
                
                // Mover marcador
                this.marker.setPosition(location);
                
                // Actualizar ubicación
                this.updateLocationFromMap(location);
                
                // Actualizar dirección
                this.state.address = results[0].formatted_address;
            } else {
                console.warn("Geocoding failed for address:", address, "Status:", status);
                alert(_t("No se pudo encontrar la dirección: ") + address);
            }
        });
    }

    searchAddress() {
        const input = document.getElementById('address-input');
        if (!input) return;

        // Si hay texto en el input, buscar directamente
        if (input.value.trim()) {
            this.searchAddressDirectly(input.value);
        } else {
            // Si no hay texto, solo enfocar el input para que el usuario escriba
            input.focus();
        }
    }

    useMyLocation() {
        if (!navigator.geolocation) {
            alert(_t("El navegador no soporta geolocalización."));
            return;
        }

        this.state.searching_address = true;
        
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const location = new google.maps.LatLng(
                    pos.coords.latitude,
                    pos.coords.longitude
                );
                
                if (this.map && this.marker) {
                    this.map.setCenter(location);
                    this.map.setZoom(17);
                    this.marker.setPosition(location);
                    this.updateLocationFromMap(location);
                    
                    // También obtener la dirección
                    this.getAddressFromCoordinates(pos.coords.latitude, pos.coords.longitude);
                }
                this.state.searching_address = false;
            },
            (err) => {
                let errorMessage = _t("No se pudo obtener la ubicación.");
                switch(err.code) {
                    case err.PERMISSION_DENIED:
                        errorMessage = _t("Permiso de ubicación denegado. Por favor habilita la ubicación en tu navegador.");
                        break;
                    case err.POSITION_UNAVAILABLE:
                        errorMessage = _t("Información de ubicación no disponible.");
                        break;
                    case err.TIMEOUT:
                        errorMessage = _t("Tiempo de espera agotado al obtener la ubicación.");
                        break;
                }
                alert(errorMessage);
                this.state.searching_address = false;
            },
            { 
                enableHighAccuracy: true, 
                timeout: 15000, 
                maximumAge: 60000 
            }
        );
    }

    openGoogleMaps() {
        // Abrir Google Maps con la ubicación actual
        if (this.state.lat && this.state.lng) {
            const mapsUrl = `https://www.google.com/maps?q=${this.state.lat},${this.state.lng}`;
            window.open(mapsUrl, '_blank');
        } else {
            // Si no hay coordenadas, abrir Google Maps normal
            window.open('https://www.google.com/maps', '_blank');
        }
    }

    confirm() {
        // VALIDACIONES COMPLETAS - TODOS LOS CAMPOS OBLIGATORIOS
        const errors = [];

        // Validar nombre del contacto
        if (!this.state.contact_name.trim()) {
            errors.push(_t("Por favor ingresa el nombre del contacto"));
        }

        // Validar teléfono
        if (!this.state.phone.trim()) {
            errors.push(_t("Por favor ingresa un número de teléfono"));
        } else if (!this.isValidPhone(this.state.phone)) {
            errors.push(_t("Por favor ingresa un número de teléfono válido"));
        }

        // Validar dirección
        if (!this.state.address.trim()) {
            errors.push(_t("Por favor ingresa una dirección de entrega"));
        }

        // Validar coordenadas
        if (!this.state.lat || !this.state.lng) {
            errors.push(_t("Por favor selecciona una ubicación en el mapa"));
        } else if (parseFloat(this.state.lat) === 0.0 && parseFloat(this.state.lng) === 0.0) {
            errors.push(_t("Por favor selecciona una ubicación válida en el mapa"));
        }

        // Mostrar errores si hay alguno
        if (errors.length > 0) {
            alert(errors.join('\n• '));
            return;
        }

        // Si todo está válido, confirmar
        const data = {
            contact_name: this.state.contact_name.trim(),
            phone: this.state.phone.trim(),
            address: this.state.address.trim(),
            notes: this.state.notes.trim(),
            lat: parseFloat(this.state.lat),
            lng: parseFloat(this.state.lng),
            maps_url: this.state.maps_url || "",
        };

        // Guardar en el pedido
        this.props.order?.set_home_delivery_data?.(data);

        // ✅ NUEVO: Opcionalmente guardar en el cliente para futuros pedidos
        this.saveToPartnerIfNeeded(data);

        this.props.close({ confirmed: true });
    }

    // NUEVO MÉTODO: Guardar datos de entrega en el cliente
    async saveToPartnerIfNeeded(deliveryData) {
        try {
            const partner = this.props.order?.get_partner?.();
            if (!partner?.id) {
                console.log("❌ No hay partner asociado al pedido");
                return;
            }

            console.log("💾 Intentando guardar datos para partner:", partner.id);

            // Solo guardar si el usuario quiere persistir estos datos
            const shouldSave = confirm(_t("¿Deseas guardar estos datos de entrega para futuros pedidos de este cliente?"));

            if (shouldSave) {
                console.log("✅ Guardando datos de entrega:", deliveryData);
                
                // Guardar en los campos delivery del partner
                await this.orm.write("res.partner", [partner.id], {
                    delivery_contact_name: deliveryData.contact_name,
                    delivery_phone: deliveryData.phone,
                    delivery_address: deliveryData.address,
                    delivery_notes: deliveryData.notes,
                    delivery_lat: deliveryData.lat,
                    delivery_lng: deliveryData.lng,
                    delivery_maps_url: deliveryData.maps_url,
                });

                console.log("✅ Datos guardados exitosamente en el partner");

                // Recargar los datos del cliente en POS
                await this.pos.loadServerData();
                
                console.log("✅ POS recargado con nuevos datos del partner");
            }
        } catch (error) {
            console.error("❌ Error guardando datos de entrega:", error);
            // Mostrar error al usuario usando el servicio corregido
            this.popup.add(ErrorPopup, {
                title: _t("Error al guardar"),
                body: _t("No se pudieron guardar los datos para futuros pedidos. Los datos se guardaron solo para este pedido."),
            });
        }
    }

    // NUEVA FUNCIÓN: Validar formato de teléfono
    isValidPhone(phone) {
        // Permitir números mexicanos: 10 dígitos, puede tener +52, espacios, guiones
        const phoneRegex = /^(\+52\s?)?(\d{2,3}[\-\s]?){2}\d{4}$/;
        // También permitir números simples de 10 dígitos
        const simplePhoneRegex = /^\d{10}$/;

        const cleanedPhone = phone.replace(/[\s\-\(\)]/g, '');
        return phoneRegex.test(phone) || simplePhoneRegex.test(cleanedPhone);
    }

    cancel() {
        this.props.close({ confirmed: false });
    }

    // ✅ VERIFICA que este método esté DENTRO de la clase (no fuera)
    async generateReport() {
        console.log("🖨️ generateReport() ejecutándose"); // ✅ Agrega este log para debug
        
        // Validaciones básicas
        if (!this.state.contact_name.trim() || !this.state.phone.trim() || !this.state.address.trim()) {
            alert(_t("Por favor completa al menos nombre, teléfono y dirección para generar el reporte."));
            return;
        }

        const data = {
            contact_name: this.state.contact_name.trim(),
            phone: this.state.phone.trim(),
            address: this.state.address.trim(),
            notes: this.state.notes.trim(),
            lat: parseFloat(this.state.lat) || 0,
            lng: parseFloat(this.state.lng) || 0,
            maps_url: this.state.maps_url || "",
        };

        await this.generateDeliveryReport(data);
    }
    // ✅ NUEVO MÉTODO: Generar reporte de entrega
    async generateDeliveryReport(deliveryData) {
        try {
            console.log("🖨️ Generando reporte de entrega...");

            const order = this.props.order;
            const partner = order?.get_partner?.() || {};

            // Datos para el reporte
            const reportData = {
                order_name: order.name || "N/A",
                order_date: new Date().toLocaleString('es-MX'),
                partner_name: partner.name || "Cliente no especificado",
                partner_phone: partner.phone || partner.mobile || "N/A",
                delivery_data: deliveryData,
                company: this.pos.company,
                pos_config: this.pos.config
            };

            // Generar PDF via RPC
            const pdfData = await this.orm.call(
                'pos.order',
                'generate_delivery_report',
                [reportData]
            );

            if (pdfData) {
                // Descargar el PDF
                this.downloadPDF(pdfData, `entrega_${order.name || 'pedido'}.pdf`);
                console.log("✅ Reporte de entrega generado exitosamente");
            }

        } catch (error) {
            console.error("❌ Error generando reporte:", error);
            this.popup.add(ErrorPopup, {
                title: _t("Error al generar reporte"),
                body: _t("No se pudo generar el reporte de entrega."),
            });
        }
    }

    // ✅ NUEVO MÉTODO: Descargar PDF
    downloadPDF(pdfData, filename) {
        try {
            // Convertir base64 a blob
            const byteCharacters = atob(pdfData);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: 'application/pdf' });

            // Crear link de descarga
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);

        } catch (error) {
            console.error("Error descargando PDF:", error);
            // Fallback: abrir en nueva pestaña
            const pdfWindow = window.open("", "_blank");
            pdfWindow.document.write(`
                <html>
                    <head><title>Reporte de Entrega</title></head>
                    <body>
                        <embed width="100%" height="100%" 
                               src="data:application/pdf;base64,${pdfData}" 
                               type="application/pdf">
                    </body>
                </html>
            `);
        }
    }

    // ✅ ACTUALIZA el método confirm() para incluir el reporte
    async confirm() {
        // VALIDACIONES COMPLETAS - TODOS LOS CAMPOS OBLIGATORIOS
        const errors = [];

        // Validar nombre del contacto
        if (!this.state.contact_name.trim()) {
            errors.push(_t("Por favor ingresa el nombre del contacto"));
        }

        // Validar teléfono
        if (!this.state.phone.trim()) {
            errors.push(_t("Por favor ingresa un número de teléfono"));
        } else if (!this.isValidPhone(this.state.phone)) {
            errors.push(_t("Por favor ingresa un número de teléfono válido"));
        }

        // Validar dirección
        if (!this.state.address.trim()) {
            errors.push(_t("Por favor ingresa una dirección de entrega"));
        }

        // Validar coordenadas
        if (!this.state.lat || !this.state.lng) {
            errors.push(_t("Por favor selecciona una ubicación en el mapa"));
        } else if (parseFloat(this.state.lat) === 0.0 && parseFloat(this.state.lng) === 0.0) {
            errors.push(_t("Por favor selecciona una ubicación válida en el mapa"));
        }

        // Mostrar errores si hay alguno
        if (errors.length > 0) {
            alert(errors.join('\n• '));
            return;
        }

        // Si todo está válido, confirmar
        const data = {
            contact_name: this.state.contact_name.trim(),
            phone: this.state.phone.trim(),
            address: this.state.address.trim(),
            notes: this.state.notes.trim(),
            lat: parseFloat(this.state.lat),
            lng: parseFloat(this.state.lng),
            maps_url: this.state.maps_url || "",
        };

        // Guardar en el pedido
        this.props.order?.set_home_delivery_data?.(data);

        // ✅ NUEVO: Preguntar si generar reporte
        const generateReport = confirm(_t("¿Deseas generar un reporte de entrega para este pedido?"));

        if (generateReport) {
            await this.generateDeliveryReport(data);
        }

        // ✅ NUEVO: Opcionalmente guardar en el cliente para futuros pedidos
        await this.saveToPartnerIfNeeded(data);

        this.props.close({ confirmed: true });
    }
}

registry.category("pos.popups").add("HomeDeliveryPopup", HomeDeliveryPopup);