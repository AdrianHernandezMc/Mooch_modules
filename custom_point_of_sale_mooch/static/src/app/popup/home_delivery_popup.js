/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";


const MUNICIPIOS_JALISCO = [
    "Acatic", "Acatlán de Juárez", "Ahualulco de Mercado", "Amacueca", 
    "Amatitán", "Ameca", "San Juanito de Escobedo", "Arandas", "El Arenal", 
    "Atemajac de Brizuela", "Atengo", "Atenguillo", "Atotonilco el Alto", 
    "Atoyac", "Autlán de Navarro", "Ayotlán", "Ayutla", "La Barca", "Bolaños", 
    "Cabo Corrientes", "Casimiro Castillo", "Cihuatlán", "Zapotlán el Grande", 
    "Cocula", "Colotlán", "Concepción de Buenos Aires", "Cuautitlán de García Barragán", 
    "Cuautla", "Cuquío", "Chapala", "Chimaltitán", "Chiquilistlán", "Degollado", 
    "Ejutla", "Encarnación de Díaz", "Etzatlán", "El Grullo", "Guachinango", 
    "Guadalajara", "Hostotipaquillo", "Huejúcar", "Huejuquilla el Alto", 
    "La Huerta", "Ixtlahuacán de los Membrillos", "Ixtlahuacán del Río", 
    "Jalostotitlán", "Jamay", "Jesús María", "Jilotlán de los Dolores", 
    "Jocotepec", "Juanacatlán", "Juchitlán", "Lagos de Moreno", "El Limón", 
    "Magdalena", "Santa María del Oro", "La Manzanilla de la Paz", "Mascota", 
    "Mazamitla", "Mexticacán", "Mezquitic", "Mixtlán", "Ocotlán", 
    "Ojuelos de Jalisco", "Pihuamo", "Poncitlán", "Puerto Vallarta", 
    "Villa Purificación", "Quitupan", "El Salto", "San Cristóbal de la Barranca", 
    "San Diego de Alejandría", "San Juan de los Lagos", "San Julián", "San Marcos", 
    "San Martín de Bolaños", "San Martín Hidalgo", "San Miguel el Alto", 
    "Gómez Farías", "San Sebastián del Oeste", "Santa María de los Ángeles", 
    "Sayula", "Tala", "Talpa de Allende", "Tamazula de Gordiano", "Tapalpa", 
    "Tecalitlán", "Techaluta de Montenegro", "Tecolotlán", "Tenamaxtlán", 
    "Teocaltiche", "Teocuitatlán de Corona", "Tepatitlán de Morelos", "Tequila", 
    "Teuchitlán", "Tizapán el Alto", "Tlajomulco de Zúñiga", "San Pedro Tlaquepaque", 
    "Tolimán", "Tomatlán", "Tonalá", "Tonaya", "Tonila", "Totatiche", "Tototlán", 
    "Tuxcacuesco", "Tuxcueca", "Tuxpan", "Unión de San Antonio", "Unión de Tula", 
    "Valle de Guadalupe", "Valle de Juárez", "San Gabriel", "Villa Corona", 
    "Villa Guerrero", "Villa Hidalgo", "Cañadas de Obregón", 
    "Yahualica de González Gallo", "Zacoalco de Torres", "Zapopan", 
    "Zapotlán del Rey", "Zapotiltic", "Zapotitlán de Vadillo", 
    "Zapotlán de Juárez", "Zapotlanejo", "San Ignacio Cerro Gordo"
].sort();

export class HomeDeliveryPopup extends Component {
    static template = "custom_point_of_sale_mooch.HomeDeliveryPopup";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");

        const order = this.props.order;
        const partner = order?.get_partner?.() || {};

        console.log("🔍 DEBUG - Campos del partner en POS:", Object.keys(partner).sort());

        // ESTADO INICIAL VACÍO - se llenará con RPC
        this.state = useState({
            // Datos de contacto (iniciales desde POS)
            contact_name: partner.name || "",
            phone: partner.phone || partner.mobile || "",
            address: this.getPartnerFullAddress(partner) || "",
            notes: "",

            // NUEVOS CAMPOS SEGMENTADOS
            street: "",
            street_number: "",
            colonia: "", // Google lo llama 'sublocality'
            city: "",
            zip: "",
            state_code: "",

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
        this.municipiosList = MUNICIPIOS_JALISCO;

        onMounted(async () => {
            //  PRIMERO cargar datos delivery del partner
            await this.loadPartnerDeliveryData(partner);
            //  LUEGO inicializar ubicación
            this.getInitialLocation();
        });

        onWillUnmount(() => {
            this.cleanup();
        });
    }

    // NUEVO MÉTODO: Cargar datos delivery del partner via RPC
    // VERSIÓN FINAL: Carga datos previos O dirección estándar de Odoo
    async loadPartnerDeliveryData(partner) {
        if (!partner?.id) {
            console.log("❌ No hay partner seleccionado al inicio");
            this.state.loading_partner_data = false;
            return;
        }

        try {
            console.log("🔄 Cargando datos del partner ID:", partner.id);

            // 1. Pedimos TODOS los datos necesarios (Delivery + Fiscales)
            const partnerData = await this.orm.read(
                "res.partner",
                [partner.id],
                [
                    // Campos de Delivery (Historial)
                    'delivery_contact_name', 'delivery_phone', 'delivery_address',
                    'delivery_notes', 'delivery_lat', 'delivery_lng', 'delivery_maps_url',
                    // Campos Fiscales (Odoo Estándar)
                    'name', 'phone', 'mobile', 
                    'street', 'street2', 'city', 'zip', 'state_id'
                ]
            );

            if (partnerData && partnerData[0]) {
                const data = partnerData[0];
                console.log("✅ Datos cargados:", data);

                // --- A. CONTACTO (Prioridad: Delivery > Fiscal > Nada) ---
                this.state.contact_name = data.delivery_contact_name || data.name || "";
                this.state.phone = data.delivery_phone || data.phone || data.mobile || "";
                this.state.notes = data.delivery_notes || "";

                // --- B. DIRECCIÓN ---
                
                // CASO 1: Tiene historial de entregas (GPS Exacto)
                if (data.delivery_address && data.delivery_lat) {
                    console.log("📍 Usando historial de entrega previo");
                    this.state.address = data.delivery_address;
                    this.state.lat = data.delivery_lat.toString();
                    this.state.lng = data.delivery_lng.toString();
                    this.state.maps_url = data.delivery_maps_url;

                    // Rellenamos también los campos manuales para que no se vean vacíos
                    this.state.street = data.street || "";
                    this.state.colonia = data.street2 || ""; // En México street2 suele ser Colonia
                    this.state.city = data.city || "";
                    this.state.zip = data.zip || "";
                } 
                // CASO 2: No tiene historial, usamos dirección de Odoo (Prioridad 1)
                else if (data.street) {
                    console.log("🏠 Usando dirección fiscal de Odoo (Primera vez)");
                    
                    // 1. Llenamos los campos del desglose
                    this.state.street = data.street || ""; 
                    this.state.street_number = ""; // Odoo guarda "Calle 123" junto, el usuario deberá separarlo si quiere
                    this.state.colonia = data.street2 || ""; 
                    this.state.city = data.city || "";
                    this.state.zip = data.zip || "";

                    // 2. Construimos la dirección completa para el mapa
                    const stateName = data.state_id ? data.state_id[1] : "";
                    const parts = [
                        data.street,
                        data.street2 ? "Col. " + data.street2 : "",
                        data.city,
                        stateName,
                        data.zip,
                        "México"
                    ];
                    
                    // Unimos quitando vacíos
                    const fullAddress = parts.filter(p => p && p.trim()).join(", ");
                    this.state.address = fullAddress;

                    // 3. Importante: Como no tenemos coordenadas, dejamos lat/lng vacíos
                    // para que el sistema sepa que debe buscar esta dirección
                    this.state.lat = "";
                    this.state.lng = "";
                    
                    // NOTA: La búsqueda real (geocoding) sucederá cuando el mapa termine de cargar
                    // gracias a la lógica que pondremos en initMap o getInitialLocation.
                }

                this.state.partner_data_loaded = true;
            }
        } catch (error) {
            console.error("❌ Error cargando datos:", error);
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

    // NUEVA FUNCIÓN: Obtener ubicación inicial (Sin GPS automático)
    getInitialLocation() {
        console.log("🔍 getInitialLocation() - Estado:", {
            loading: this.state.loading_partner_data
        });

        // 1. ESPERAR a que terminen de cargar los datos del partner
        if (this.state.loading_partner_data) {
            setTimeout(() => this.getInitialLocation(), 100);
            return;
        }

        // 2. CASO A: Coordenadas EXACTAS guardadas (Historial de entregas)
        if (this.state.lat && this.state.lng && 
            parseFloat(this.state.lat) !== 0.0 && 
            parseFloat(this.state.lng) !== 0.0) {
            
            console.log("✅ Usando coordenadas EXACTAS guardadas");
            this.state.getting_location = false;
            this.loadGoogleMaps();
            return;
        }

        // 3. CASO B: Dirección de TEXTO detectada en Odoo (pero sin coordenadas aún)
        // Esto pasa cuando loadPartnerDeliveryData encontró 'street', 'city', etc.
        if (this.state.address && this.state.address.length > 5) {
            console.log("🔎 Dirección de texto encontrada, buscando en mapa...");
            this.state.getting_location = false;
            this.loadGoogleMaps();
            
            // Esperamos un momento a que el mapa cargue y lanzamos la búsqueda automática
            // para convertir el texto en coordenadas y poner el pin.
            setTimeout(() => {
                this.searchAddressDirectly(this.state.address);
            }, 1000); 
            return;
        }

        // 4. CASO C: Nada de nada (Cliente nuevo o sin dirección)
        // -> Usamos la UBICACIÓN POR DEFECTO (Tlajomulco)
        console.log("📍 Usando ubicación por defecto: Tlajomulco");

        // Coordenadas aproximadas de C. Porfirio Díaz 90, Tlajomulco
        this.state.lat = "20.477240"; 
        this.state.lng = "-103.451949";
        this.state.maps_url = `https://maps.google.com/?q=${this.state.lat},${this.state.lng}`;

        // Llenamos la barra gris general para que el mapa sepa qué mostrar
        this.state.address = "C. Porfirio Díaz 90, 45640 Tlajomulco de Zúñiga, Jal., México";

        // IMPORTANTE: Dejamos los campos de desglose VACÍOS para que el usuario
        // pueda empezar a escribir desde cero si lo desea.
        this.state.street = "";
        this.state.street_number = "";
        this.state.colonia = "";
        this.state.zip = "";
        this.state.city = "";

        this.state.getting_location = false;
        this.loadGoogleMaps();
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
                componentRestrictions: { country: 'mx' }, 
                // ✅ CAMBIO 1: Agregamos 'address_components' aquí para recibir los datos separados
                fields: ['formatted_address', 'geometry', 'name', 'address_components']
            });

            // Vincular el autocompletado al área visible del mapa.
            if (this.map) {
                this.autocomplete.bindTo('bounds', this.map);
            }

            // Cuando se selecciona una dirección del autocomplete
            this.autocomplete.addListener('place_changed', () => {
                const place = this.autocomplete.getPlace();

                if (!place.geometry) {
                    // Si el usuario presiona Enter sin seleccionar una opción de la lista,
                    // a veces Google no devuelve geometría, intentamos buscarla manualmente.
                    console.warn("No se pudo obtener la ubicación precisa, buscando por texto...");
                    this.searchAddressDirectly(place.name); 
                    return;
                }

                // Centrar mapa en la ubicación seleccionada
                this.map.setCenter(place.geometry.location);
                this.map.setZoom(17);

                // Mover marcador
                this.marker.setPosition(place.geometry.location);

                // Actualizar coordenadas (lat/lng)
                this.updateLocationFromMap(place.geometry.location);

                // Actualizar dirección completa (para mostrar en el input)
                if (place.formatted_address) {
                    this.state.address = place.formatted_address;
                }

                // ✅ CAMBIO 2: Extraer y guardar los datos segmentados
                if (place.address_components) {
                    // Llamamos a la función auxiliar que creamos anteriormente
                    const segmented = this.extractAddressData(place.address_components);
                    
                    // Guardamos en el estado
                    this.state.street = segmented.street;
                    this.state.street_number = segmented.street_number;
                    this.state.colonia = segmented.colonia;
                    this.state.city = segmented.city;
                    this.state.zip = segmented.zip;
                    this.state.state_code = segmented.state_code;
                    
                    console.log("✅ Dirección segmentada guardada:", segmented);
                }
            });

            // Prevenir envío del formulario al presionar Enter
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    // Si hay texto en el input, buscar esa dirección manualmente
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

                    // ✅ NUEVO: Extraer componentes al mover el pin
                    const segmented = this.extractAddressData(results[0].address_components);
                    this.state.street = segmented.street;
                    this.state.street_number = segmented.street_number;
                    this.state.colonia = segmented.colonia;
                    this.state.city = segmented.city;
                    this.state.zip = segmented.zip;
                    this.state.state_code = segmented.state_code;

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

        const geocodeRequest = {
            address: address,
            componentRestrictions: { country: 'mx' }
        };

        if (this.map) {
            geocodeRequest.bounds = this.map.getBounds();
        }

        this.geocoder.geocode(geocodeRequest, (results, status) => {
            this.state.searching_address = false;

            if (status === 'OK' && results[0]) {
                const location = results[0].geometry.location;

                // Centrar mapa y mover marcador
                this.map.setCenter(location);
                this.map.setZoom(17);
                this.marker.setPosition(location);

                // Actualizar coordenadas
                this.state.lat = location.lat().toFixed(6);
                this.state.lng = location.lng().toFixed(6);
                this.state.maps_url = `https://maps.google.com/?q=${this.state.lat},${this.state.lng}`;

                // ⚠️ IMPORTANTE: 
                // Si la búsqueda vino de los campos manuales, NO sobrescribimos 
                // 'street', 'number', etc. con la respuesta de Google, 
                // solo actualizamos la dirección formateada general.
                
                // Solo si la dirección en el estado está vacía (primera carga), la llenamos.
                if (!this.state.address) {
                    this.state.address = results[0].formatted_address;
                }
                
                console.log("📍 Ubicación actualizada por búsqueda manual de campos");
            } else {
                console.warn("No se encontró la dirección:", address);
                // No mostramos alert aquí para no interrumpir al usuario mientras escribe
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
            address: this.state.address.trim(), // Dirección completa formateada
            notes: this.state.notes.trim(),
            lat: parseFloat(this.state.lat),
            lng: parseFloat(this.state.lng),
            maps_url: this.state.maps_url || "",

            // AGREGAMOS LO SEGMENTADO
            street: this.state.street,
            street_number: this.state.street_number,
            colonia: this.state.colonia,
            city: this.state.city,
            zip: this.state.zip,
            state_code: this.state.state_code
        };

        // Guardar en el pedido
        this.props.order?.set_home_delivery_data?.(data);

        // NUEVO: Opcionalmente guardar en el cliente para futuros pedidos
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

                // ✅ ESTA ES LA LÍNEA QUE FALTABA:
                const fullStreet = `${deliveryData.street || ''} ${deliveryData.street_number || ''}`.trim();

                // Guardar en los campos delivery del partner
                await this.orm.write("res.partner", [partner.id], {
                    delivery_contact_name: deliveryData.contact_name,
                    delivery_phone: deliveryData.phone,
                    delivery_address: deliveryData.address,
                    delivery_notes: deliveryData.notes,
                    delivery_lat: deliveryData.lat,
                    delivery_lng: deliveryData.lng,
                    delivery_maps_url: deliveryData.maps_url,

                    // CAMPOS ESTÁNDAR DE ODOO (Address format)
                    // Ahora sí funciona porque 'fullStreet' ya está definida arriba
                    street: fullStreet || deliveryData.address,
                    street2: deliveryData.colonia,
                    city: deliveryData.city,
                    zip: deliveryData.zip,
                });

                console.log("✅ Datos guardados exitosamente en el partner");

                // Recargar los datos del cliente en POS (Optimizado para solo recargar partners)
                await this.pos.load_new_partners();

                console.log("✅ POS recargado con nuevos datos del partner");
            }
        } catch (error) {
            console.error("❌ Error guardando datos de entrega:", error);
            this.popup.add(ErrorPopup, {
                title: _t("Error al guardar"),
                body: _t("No se pudieron guardar los datos en la ficha del cliente (aunque sí se usarán para este pedido)."),
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

    // VERIFICA que este método esté DENTRO de la clase (no fuera)
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
    // NUEVO MÉTODO: Generar reporte de entrega
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

    // NUEVO MÉTODO: Descargar PDF
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

    // ACTUALIZA el método confirm() para incluir el reporte
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

        // NUEVO: Preguntar si generar reporte
        const generateReport = confirm(_t("¿Deseas generar un reporte de entrega para este pedido?"));

        if (generateReport) {
            await this.generateDeliveryReport(data);
        }

        // NUEVO: Opcionalmente guardar en el cliente para futuros pedidos
        await this.saveToPartnerIfNeeded(data);

        this.props.close({ confirmed: true });
    }

    // NUEVO MÉTODO: Extraer datos segmentados de Google
    extractAddressData(components) {
        let data = { street: '', street_number: '', colonia: '', city: '', state_code: '', zip: '' };
        if (!components) return data;

        for (const component of components) {
            const types = component.types;
            if (types.includes('route')) data.street = component.long_name;
            if (types.includes('street_number')) data.street_number = component.long_name;
            if (types.includes('sublocality') || types.includes('neighborhood') || types.includes('sublocality_level_1')) data.colonia = component.long_name;
            if (types.includes('locality')) data.city = component.long_name;
            if (types.includes('administrative_area_level_1')) data.state_code = component.short_name;
            if (types.includes('postal_code')) data.zip = component.long_name;
        }

        console.log("📍 Datos segmentados extraídos:", data);
        return data;
    }
    // NUEVO: Reconstruir dirección desde los campos específicos y buscar
    async updateFromSpecificFields() {
        // 1. Obtener valores actuales (asegurando que no sean null/undefined)
        const street = this.state.street || '';
        const number = this.state.street_number || '';
        const col = this.state.colonia || '';
        const zip = this.state.zip || '';
        const city = this.state.city || '';
        const state = this.state.state_code || '';

        // 2. Construir el string de búsqueda inteligente
        // Prioridad: Calle + Numero + Colonia + Ciudad + CP
        let searchComponents = [];
        
        if (street) searchComponents.push(street);
        if (number) searchComponents.push(number);
        if (col) searchComponents.push("Col. " + col);
        if (city) searchComponents.push(city);
        if (state) searchComponents.push(state);
        if (zip) searchComponents.push(zip);

        // Unir todo con comas
        const fullQuery = searchComponents.join(', ');

        if (fullQuery.trim().length > 5) { // Solo buscar si hay algo sustancial
            console.log("🔄 Buscando desde campos detallados:", fullQuery);
            
            // 3. Actualizar la barra principal visualmente
            this.state.address = fullQuery;
            
            // 4. Mandar buscar al mapa (sin disparar el Autocomplete, directo al Geocoder)
            this.searchAddressDirectly(fullQuery);
        }
    }
}

registry.category("pos.popups").add("HomeDeliveryPopup", HomeDeliveryPopup);