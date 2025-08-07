# 🐧 Mooch Custom Odoo Modules

![Odoo](https://img.shields.io/badge/Odoo-17%2F18-7A962B) ![Python](https://img.shields.io/badge/Python-3.10-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow)

Este repositorio agrupa una serie de módulos personalizados desarrollados para **Odoo 17/18** bajo la marca **Mooch**. Cada módulo extiende o mejora funcionalidades estándar de Odoo en áreas de conexión SQL, gestión de crédito, Punto de Venta, compras, reportes, inventario y productos.

---

## 📋 Tabla de Contenidos

1. [⚙️ Requisitos](#requisitos)  
2. [🚀 Instalación](#instalación)  
3. [🔍 Visión General de Módulos](#visión-general-de-módulos)  
   - [🗄️ conection_sql_mooch](#conection_sql_mooch)  
   - [💳 custom_credit_mooch](#custom_credit_mooch)  
   - [🛒 custom_point_of_sale_mooch](#custom_point_of_sale_mooch)  
   - [🛍️ custom_purchase_mooch](#custom_purchase_mooch)  
   - [📊 custom_reports_mooch](#custom_reports_mooch)  
   - [📦 custom_stock_mooch](#custom_stock_mooch)  
   - [🔧 product_mooch](#product_mooch)  
4. [📖 Uso Básico](#uso-básico)  
5. [🤝 Contribuciones](#contribuciones)  
6. [📝 Licencia](#licencia)  

---

## ⚙️ Requisitos

- **Odoo** versión 17 o 18  
- **Python** 3.10+  
- Dependencias mínimas (instaladas en tu entorno virtual de Odoo):
  - `psycopg2`
  - `reportlab`
  - `html2canvas`, `jsPDF` (para exportar organigramas)
  - Otras dependencias propias de Odoo (ver `requirements.txt` de Odoo)

---

## 🚀 Instalación

```bash
cd /ruta/a/tu/odoo/custom_addons
git clone git@github.com:AdrianHernandezMooch/mooch-custom-addons.git
# Asegúrate de incluir la ruta en addons_path de Odoo
sudo systemctl restart odoo
```

1. Abre Odoo en modo desarrollador y actualiza la lista de Apps.  
2. Busca e instala cada módulo según su nombre técnico.  

---

## 🔍 Visión General de Módulos

### 🗄️ conection_sql_mooch

- **Descripción**: Facilita conexiones directas a bases de datos externas vía SQL.  
- **Características**:
  - Configuración de parámetros de conexión (`host`, `port`, `user`, `password`, `dbname`).
  - Métodos para ejecutar consultas y volcar resultados en modelos Odoo.  
- **Dependencias**: Ninguna.

### 💳 custom_credit_mooch

- **Descripción**: Añade gestión de precio y ventas a crédito.  
- **Características**:
  - Campo `credit_price` en `product.template`.  
  - Integración en ventas normales y Punto de Venta.  
  - Reportes de cuentas por cobrar.  
- **Dependencias**: `sale`.

### 🛒 custom_point_of_sale_mooch

- **Descripción**: Personalizaciones para el Punto de Venta.  
- **Características**:
  - Devolución de productos desde el POS.  
  - Alertas de efectivo en caja (umbral configurable).  
  - Botones y popups OWL para crédito.  
- **Dependencias**: `point_of_sale`, `custom_credit_mooch`.

### 🛍️ custom_purchase_mooch

- **Descripción**: Mejoras al flujo de compras.  
- **Características**:
  - Descuento global en órdenes de compra.  
  - Validación de presupuesto por departamento.  
  - Wizard de selección múltiple de productos.  
- **Dependencias**: `purchase`, `account`.

### 📊 custom_reports_mooch

- **Descripción**: Reportes personalizados y plantillas QWeb.  
- **Características**:
  - Reporte de Orden de Compra con campos adicionales.  
  - Reportes de termopanel con métricas.  
- **Dependencias**: `report`, `purchase`.

### 📦 custom_stock_mooch

- **Descripción**: Extensión de gestión de inventario.  
- **Características**:
  - Segmentación de pickings por evento.  
  - Devoluciones mejoradas con selección de líneas.  
- **Dependencias**: `stock`, `custom_purchase_mooch`.

### 🔧 product_mooch

- **Descripción**: Lógica de negocio para productos.  
- **Características**:
  - Cálculo de márgenes y precios.  
  - Generación de códigos internos.  
  - Gestión de atributos (departamento, tipo, color, talla).  
- **Dependencias**: `product`, `barcode`.

---

## 📖 Uso Básico

1. Configura parámetros en **Ajustes → Parámetros**.  
2. Navega a los menús (Ventas, Compras, Inventario, POS, Reportes).  
3. Prueba las funcionalidades y consulta logs en nivel DEBUG si es necesario.  

---

## 🤝 Contribuciones

¡Bienvenides! Para aportar:

```bash
git clone git@github.com:AdrianHernandezMooch/mooch-custom-addons.git
cd mooch-custom-addons
git checkout -b feature/mi-cambio
# Realiza cambios, añade tests, documenta
git push origin feature/mi-cambio
```

Luego abre un Pull Request describiendo tu mejora.

---

## 📝 Licencia

Distribuido bajo la **Licencia MIT**. Consulta `LICENSE` para más detalles.
