# ?? Mooch Custom Odoo Modules

![Odoo](https://img.shields.io/badge/Odoo-17%2F18-7A962B) ![Python](https://img.shields.io/badge/Python-3.10-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-yellow)

Este repositorio agrupa una serie de m車dulos personalizados desarrollados para **Odoo 17/18** bajo la marca **Mooch**. Cada m車dulo extiende o mejora funcionalidades est芍ndar de Odoo en 芍reas de conexi車n SQL, gesti車n de cr谷dito, Punto de Venta, compras, reportes, inventario y productos.

---

## ?? Tabla de Contenidos

1. [?? Requisitos](#requisitos)  
2. [?? Instalaci車n](#instalaci車n)  
3. [?? Visi車n General de M車dulos](#visi車n-general-de-m車dulos)  
   - [??? conection_sql_mooch](#conection_sql_mooch)  
   - [?? custom_credit_mooch](#custom_credit_mooch)  
   - [?? custom_point_of_sale_mooch](#custom_point_of_sale_mooch)  
   - [??? custom_purchase_mooch](#custom_purchase_mooch)  
   - [?? custom_reports_mooch](#custom_reports_mooch)  
   - [?? custom_stock_mooch](#custom_stock_mooch)  
   - [?? product_mooch](#product_mooch)  
4. [?? Uso B芍sico](#uso-b芍sico)  
5. [?? Contribuciones](#contribuciones)  
6. [?? Licencia](#licencia)  

---

## ?? Requisitos

- **Odoo** versi車n 17 o 18  
- **Python** 3.10+  
- Dependencias m赤nimas (instaladas en tu entorno virtual de Odoo):
  - `psycopg2`
  - `reportlab`
  - `html2canvas`, `jsPDF` (para exportar organigramas)
  - Otras dependencias propias de Odoo (ver `requirements.txt` de Odoo)

---

## ?? Instalaci車n

```bash
cd /ruta/a/tu/odoo/custom_addons
git clone git@github.com:AdrianHernandezMooch/mooch-custom-addons.git
# Aseg迆rate de incluir la ruta en addons_path de Odoo
sudo systemctl restart odoo
```

1. Abre Odoo en modo desarrollador y actualiza la lista de Apps.  
2. Busca e instala cada m車dulo seg迆n su nombre t谷cnico.  

---

## ?? Visi車n General de M車dulos

### ??? conection_sql_mooch

- **Descripci車n**: Facilita conexiones directas a bases de datos externas v赤a SQL.  
- **Caracter赤sticas**:
  - Configuraci車n de par芍metros de conexi車n (`host`, `port`, `user`, `password`, `dbname`).
  - M谷todos para ejecutar consultas y volcar resultados en modelos Odoo.  
- **Dependencias**: Ninguna.

### ?? custom_credit_mooch

- **Descripci車n**: A?ade gesti車n de precio y ventas a cr谷dito.  
- **Caracter赤sticas**:
  - Campo `credit_price` en `product.template`.  
  - Integraci車n en ventas normales y Punto de Venta.  
  - Reportes de cuentas por cobrar.  
- **Dependencias**: `sale`.

### ?? custom_point_of_sale_mooch

- **Descripci車n**: Personalizaciones para el Punto de Venta.  
- **Caracter赤sticas**:
  - Devoluci車n de productos desde el POS.  
  - Alertas de efectivo en caja (umbral configurable).  
  - Botones y popups OWL para cr谷dito.  
- **Dependencias**: `point_of_sale`, `custom_credit_mooch`.

### ??? custom_purchase_mooch

- **Descripci車n**: Mejoras al flujo de compras.  
- **Caracter赤sticas**:
  - Descuento global en 車rdenes de compra.  
  - Validaci車n de presupuesto por departamento.  
  - Wizard de selecci車n m迆ltiple de productos.  
- **Dependencias**: `purchase`, `account`.

### ?? custom_reports_mooch

- **Descripci車n**: Reportes personalizados y plantillas QWeb.  
- **Caracter赤sticas**:
  - Reporte de Orden de Compra con campos adicionales.  
  - Reportes de termopanel con m谷tricas.  
- **Dependencias**: `report`, `purchase`.

### ?? custom_stock_mooch

- **Descripci車n**: Extensi車n de gesti車n de inventario.  
- **Caracter赤sticas**:
  - Segmentaci車n de pickings por evento.  
  - Devoluciones mejoradas con selecci車n de l赤neas.  
- **Dependencias**: `stock`, `custom_purchase_mooch`.

### ?? product_mooch

- **Descripci車n**: L車gica de negocio para productos.  
- **Caracter赤sticas**:
  - C芍lculo de m芍rgenes y precios.  
  - Generaci車n de c車digos internos.  
  - Gesti車n de atributos (departamento, tipo, color, talla).  
- **Dependencias**: `product`, `barcode`.

---

## ?? Uso B芍sico

1. Configura par芍metros en **Ajustes ↙ Par芍metros**.  
2. Navega a los men迆s (Ventas, Compras, Inventario, POS, Reportes).  
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

Distribuido bajo la **Licencia MIT**. Consulta `LICENSE` para m芍s detalles.
