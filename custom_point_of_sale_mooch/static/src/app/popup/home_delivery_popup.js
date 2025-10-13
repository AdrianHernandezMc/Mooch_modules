/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export class HomeDeliveryPopup extends Component {
    static template = "custom_point_of_sale_mooch.HomeDeliveryPopup";
    
    setup() {
        this.pos = usePos();
        const partner = this.props.order?.get_partner?.() || {};
        const existing = this.props.order?.get_home_delivery_data?.() || {};
        
        this.state = useState({
            // Datos de contacto
            contact_name: existing.contact_name || partner.name || "",
            phone: existing.phone || partner.phone || partner.mobile || "",
            address: existing.address || partner.street || "",
            notes: existing.notes || "",
            
            // Ubicación
            lat: existing.lat || "",
            lng: existing.lng || "",
            maps_url: existing.maps_url || "",
            
            // Estado del mapa
            map_loaded: false,
            searching_address: false,
            selected_location: null
        });

        this.map = null;
        this.marker = null;
        this.autocomplete = null;

        onMounted(() => {
            this.loadGoogleMaps();
        });

        onWillUnmount(() => {
            this.cleanup();
        });
    }

    cleanup() {
        // Limpiar eventos y referencias
        if (this.autocomplete) {
            this.autocomplete = null;
        }
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
            // Cargar Google Maps con la nueva librería places
            await new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = `https://maps.googleapis.com/maps/api/js?key=${this.props.config.google_maps_api_key}&loading=async&libraries=places,marker`;
                script.async = true;
                script.defer = true;
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            });
            
            this.state.map_loaded = true;
            setTimeout(() => this.initMap(), 500); // Dar más tiempo para la carga
        } catch (error) {
            console.error("Error loading Google Maps:", error);
            this.state.map_loaded = true;
        }
    }

    async initMap() {
        if (!this.state.map_loaded || !window.google || !window.google.maps) {
            console.warn("Google Maps not available");
            return;
        }

        try {
            const { Map } = await google.maps.importLibrary("maps");
            const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");
            const { PlaceAutocompleteElement } = await google.maps.importLibrary("places");

            // Configurar ubicación por defecto
            const defaultLat = this.state.lat ? parseFloat(this.state.lat) : 20.659698;
            const defaultLng = this.state.lng ? parseFloat(this.state.lng) : -103.349609;
            const defaultLocation = { lat: defaultLat, lng: defaultLng };

            // Crear mapa
            this.map = new Map(document.getElementById('delivery-map'), {
                center: defaultLocation,
                zoom: 15,
                mapId: 'delivery-map-id',
                streetViewControl: true,
                mapTypeControl: true,
                fullscreenControl: true
            });

            // Crear marcador avanzado
            this.marker = new AdvancedMarkerElement({
                map: this.map,
                position: defaultLocation,
                title: "Ubicación de entrega",
                gmpDraggable: true
            });

            // Configurar autocomplete con la nueva API
            this.setupAutocomplete(PlaceAutocompleteElement);

            // Configurar eventos del mapa
            this.setupMapEvents();

        } catch (error) {
            console.error("Error initializing map:", error);
            this.fallbackToManualMode();
        }
    }

    setupAutocomplete(PlaceAutocompleteElement) {
        const addressInput = document.getElementById('address-input');
        if (!addressInput) return;

        try {
            // Crear el elemento de autocomplete
            this.autocomplete = new PlaceAutocompleteElement({
                inputElement: addressInput,
                placeTypeFilter: 'address',
                componentRestrictions: { country: 'mx' }
            });

            // Escuchar cambios en la selección
            this.autocomplete.addEventListener('gmp-placeselect', async (event) => {
                const place = event.place;
                if (place && place.location) {
                    this.map.setCenter(place.location);
                    this.marker.position = place.location;
                    
                    // Actualizar coordenadas
                    this.updateLocationFromMap(place.location);
                    
                    // Obtener y actualizar dirección
                    try {
                        const address = await this.getFormattedAddress(place);
                        this.state.address = address;
                    } catch (error) {
                        console.warn("Could not get formatted address:", error);
                    }
                }
            });

        } catch (error) {
            console.error("Error setting up autocomplete:", error);
            this.fallbackToManualAutocomplete();
        }
    }

    async getFormattedAddress(place) {
        // Intentar obtener la dirección formateada del lugar
        if (place.formattedAddress) {
            return place.formattedAddress;
        }
        
        // Si no está disponible, construir manualmente
        const components = place.addressComponents || [];
        let address = '';
        
        if (components.length > 0) {
            // Construir dirección básica
            const street = components.find(c => c.types.includes('route'))?.longText || '';
            const number = components.find(c => c.types.includes('street_number'))?.longText || '';
            const locality = components.find(c => c.types.includes('locality'))?.longText || '';
            const state = components.find(c => c.types.includes('administrative_area_level_1'))?.shortText || '';
            
            address = [street, number].filter(Boolean).join(' ');
            if (locality) address += `, ${locality}`;
            if (state) address += `, ${state}`;
        }
        
        return address || place.displayName || 'Dirección no disponible';
    }

    setupMapEvents() {
        // Evento cuando se mueve el marcador
        this.marker.addListener('gmp-dragend', (event) => {
            this.updateLocationFromMap(this.marker.position);
        });

        // Evento cuando se hace clic en el mapa
        this.map.addListener('click', (event) => {
            this.marker.position = event.latLng;
            this.updateLocationFromMap(event.latLng);
        });
    }

    updateLocationFromMap(latLng) {
        if (!latLng || (typeof latLng.lat !== 'function' && typeof latLng.lat !== 'number')) {
            console.warn("Invalid latLng object:", latLng);
            return;
        }

        try {
            // Manejar tanto la nueva como la vieja API
            const lat = typeof latLng.lat === 'function' ? latLng.lat() : latLng.lat;
            const lng = typeof latLng.lng === 'function' ? latLng.lng() : latLng.lng;
            
            this.state.lat = Number(lat).toFixed(6);
            this.state.lng = Number(lng).toFixed(6);
            this.state.maps_url = `https://maps.google.com/?q=${this.state.lat},${this.state.lng}`;
            
            // Obtener dirección desde coordenadas
            this.getAddressFromCoordinates(lat, lng);
        } catch (error) {
            console.error("Error updating location from map:", error);
        }
    }

    async getAddressFromCoordinates(lat, lng) {
        if (!window.google || !window.google.maps) return;

        try {
            const { Geocoder } = await google.maps.importLibrary("geocoding");
            const geocoder = new Geocoder();
            
            geocoder.geocode({ location: { lat, lng } }, (results, status) => {
                if (status === 'OK' && results[0]) {
                    this.state.address = results[0].formatted_address;
                }
            });
        } catch (error) {
            console.error("Error in reverse geocoding:", error);
        }
    }

    fallbackToManualMode() {
        console.log("Falling back to manual mode without map");
        // El formulario seguirá funcionando sin el mapa
    }

    fallbackToManualAutocomplete() {
        console.log("Falling back to manual address input");
        // El usuario podrá ingresar la dirección manualmente
    }

    useMyLocation() {
        if (!navigator.geolocation) {
            alert(_t("El navegador no soporta geolocalización."));
            return;
        }

        this.state.searching_address = true;
        
        navigator.geolocation.getCurrentPosition(
            async (pos) => {
                const location = {
                    lat: pos.coords.latitude,
                    lng: pos.coords.longitude
                };
                
                if (this.map && this.marker) {
                    this.map.setCenter(location);
                    this.marker.position = location;
                    this.updateLocationFromMap(location);
                }
                this.state.searching_address = false;
            },
            (err) => {
                alert(_t("No se pudo obtener la ubicación: ") + err.message);
                this.state.searching_address = false;
            },
            { 
                enableHighAccuracy: true, 
                timeout: 15000, 
                maximumAge: 60000 
            }
        );
    }

    searchAddress() {
        const addressInput = document.getElementById('address-input');
        if (addressInput) {
            addressInput.focus();
        }
    }

    confirm() {
        const data = {
            contact_name: this.state.contact_name || "",
            phone: this.state.phone || "",
            address: this.state.address || "",
            notes: this.state.notes || "",
            lat: parseFloat(this.state.lat) || 0.0,
            lng: parseFloat(this.state.lng) || 0.0,
            maps_url: this.state.maps_url || "",
        };
        this.props.order?.set_home_delivery_data?.(data);
        this.props.close({ confirmed: true });
    }

    cancel() { 
        this.props.close({ confirmed: false });
    }
}

registry.category("pos.popups").add("HomeDeliveryPopup", HomeDeliveryPopup);