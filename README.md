# ?? Mooch Custom Odoo Modules

![Odoo](https://img.shields.io/badge/Odoo-17%2F18-7A962B) ![Python](https://img.shields.io/badge/Python-3.10-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow)

Este repositorio agrupa una serie de m��dulos personalizados desarrollados para **Odoo 17/18** bajo la marca **Mooch**. Cada m��dulo extiende o mejora funcionalidades est��ndar de Odoo en ��reas de conexi��n SQL, gesti��n de cr��dito, Punto de Venta, compras, reportes, inventario y productos.

---

## ?? Tabla de Contenidos

1. [?? Requisitos](#requisitos)  
2. [?? Instalaci��n](#instalaci��n)  
3. [?? Visi��n General de M��dulos](#visi��n-general-de-m��dulos)  
   - [??? conection_sql_mooch](#conection_sql_mooch)  
   - [?? custom_credit_mooch](#custom_credit_mooch)  
   - [?? custom_point_of_sale_mooch](#custom_point_of_sale_mooch)  
   - [??? custom_purchase_mooch](#custom_purchase_mooch)  
   - [?? custom_reports_mooch](#custom_reports_mooch)  
   - [?? custom_stock_mooch](#custom_stock_mooch)  
   - [?? product_mooch](#product_mooch)  
4. [?? Uso B��sico](#uso-b��sico)  
5. [?? Contribuciones](#contribuciones)  
6. [?? Licencia](#licencia)  

---

## ?? Requisitos

- **Odoo** versi��n 17 o 18  
- **Python** 3.10+  
- Dependencias m��nimas (instaladas en tu entorno virtual de Odoo):
  - `psycopg2`
  - `reportlab`
  - `html2canvas`, `jsPDF` (para exportar organigramas)
  - Otras dependencias propias de Odoo (ver `requirements.txt` de Odoo)

---

## ?? Instalaci��n

```bash
cd /ruta/a/tu/odoo/custom_addons
git clone git@github.com:AdrianHernandezMooch/mooch-custom-addons.git
# Aseg��rate de incluir la ruta en addons_path de Odoo
sudo systemctl restart odoo
```

1. Abre Odoo en modo desarrollador y actualiza la lista de Apps.  
2. Busca e instala cada m��dulo seg��n su nombre t��cnico.  

---

## ?? Visi��n General de M��dulos

### ??? conection_sql_mooch

- **Descripci��n**: Facilita conexiones directas a bases de datos externas v��a SQL.  
- **Caracter��sticas**:
  - Configuraci��n de par��metros de conexi��n (`host`, `port`, `user`, `password`, `dbname`).
  - M��todos para ejecutar consultas y volcar resultados en modelos Odoo.  
- **Dependencias**: Ninguna.

### ?? custom_credit_mooch

- **Descripci��n**: A?ade gesti��n de precio y ventas a cr��dito.  
- **Caracter��sticas**:
  - Campo `credit_price` en `product.template`.  
  - Integraci��n en ventas normales y Punto de Venta.  
  - Reportes de cuentas por cobrar.  
- **Dependencias**: `sale`.

### ?? custom_point_of_sale_mooch

- **Descripci��n**: Personalizaciones para el Punto de Venta.  
- **Caracter��sticas**:
  - Devoluci��n de productos desde el POS.  
  - Alertas de efectivo en caja (umbral configurable).  
  - Botones y popups OWL para cr��dito.  
- **Dependencias**: `point_of_sale`, `custom_credit_mooch`.

### ??? custom_purchase_mooch

- **Descripci��n**: Mejoras al flujo de compras.  
- **Caracter��sticas**:
  - Descuento global en ��rdenes de compra.  
  - Validaci��n de presupuesto por departamento.  
  - Wizard de selecci��n m��ltiple de productos.  
- **Dependencias**: `purchase`, `account`.

### ?? custom_reports_mooch

- **Descripci��n**: Reportes personalizados y plantillas QWeb.  
- **Caracter��sticas**:
  - Reporte de Orden de Compra con campos adicionales.  
  - Reportes de termopanel con m��tricas.  
- **Dependencias**: `report`, `purchase`.

### ?? custom_stock_mooch

- **Descripci��n**: Extensi��n de gesti��n de inventario.  
- **Caracter��sticas**:
  - Segmentaci��n de pickings por evento.  
  - Devoluciones mejoradas con selecci��n de l��neas.  
- **Dependencias**: `stock`, `custom_purchase_mooch`.

### ?? product_mooch

- **Descripci��n**: L��gica de negocio para productos.  
- **Caracter��sticas**:
  - C��lculo de m��rgenes y precios.  
  - Generaci��n de c��digos internos.  
  - Gesti��n de atributos (departamento, tipo, color, talla).  
- **Dependencias**: `product`, `barcode`.

---

## ?? Uso B��sico

1. Configura par��metros en **Ajustes �� Par��metros**.  
2. Navega a los men��s (Ventas, Compras, Inventario, POS, Reportes).  
3. Prueba las funcionalidades y consulta logs en nivel DEBUG si es necesario.  

---

## ?? Contribuciones

?Bienvenides! Para aportar:

```bash
git clone git@github.com:AdrianHernandezMooch/mooch-custom-addons.git
cd mooch-custom-addons
git checkout -b feature/mi-cambio
# Realiza cambios, a?ade tests, documenta
git push origin feature/mi-cambio
```

Luego abre un Pull Request describiendo tu mejora.

---

## ?? Licencia

Distribuido bajo la **Licencia MIT**. Consulta `LICENSE` para m��s detalles.
