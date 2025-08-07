:penguin: Mooch Custom Odoo Modules

  

Este repositorio agrupa una serie de m��dulos personalizados desarrollados para Odoo 17/18 bajo la marca Mooch. Cada m��dulo extiende o mejora funcionalidades est��ndar de Odoo en ��reas de conexi��n SQL, gesti��n de cr��dito, Punto de Venta, compras, reportes, inventario y productos.

:clipboard: Tabla de Contenidos

:gear: Requisitos

:rocket: Instalaci��n

:mag: Visi��n General de M��dulos

:file_cabinet: conection_sql_mooch

:credit_card: custom_credit_mooch

:shopping_cart: custom_point_of_sale_mooch

:shopping_bags: custom_purchase_mooch

:bar_chart: custom_reports_mooch

:package: custom_stock_mooch

:wrench: product_mooch

:book: Uso B��sico

:handshake: Contribuciones

:memo: Licencia

:gear: Requisitos

Odoo versi��n 17 o 18

Python 3.10+

Dependencias m��nimas (instaladas en tu entorno virtual de Odoo):

psycopg2

reportlab

html2canvas, jsPDF (para exportar organigramas)

Otras dependencias propias de Odoo (ver requirements.txt de Odoo)

:rocket: Instalaci��n

cd /ruta/a/tu/odoo/custom_addons
git clone git@github.com:AdrianHernandezMooch/mooch-custom-addons.git
# Aseg��rate de incluir la ruta en addons_path de Odoo
sudo systemctl restart odoo

Abre Odoo en modo desarrollador y actualiza la lista de Apps.

Busca e instala cada m��dulo seg��n su nombre t��cnico.

:mag: Visi��n General de M��dulos

:file_cabinet: conection_sql_mooch

Descripci��n: Facilita conexiones directas a bases de datos externas v��a SQL.

Caracter��sticas:

Configuraci��n de par��metros de conexi��n (host, port, user, password, dbname).

M��todos para ejecutar consultas y volcar resultados en modelos Odoo.

Dependencias: Ninguna.

:credit_card: custom_credit_mooch

Descripci��n: A?ade gesti��n de precio y ventas a cr��dito.

Caracter��sticas:

Campo credit_price en product.template.

Integraci��n en ventas normales y Punto de Venta.

Reportes de cuentas por cobrar.

Dependencias: sale.

:shopping_cart: custom_point_of_sale_mooch

Descripci��n: Personalizaciones para el Punto de Venta.

Caracter��sticas:

Devoluci��n de productos desde el POS.

Alertas de efectivo en caja (umbral configurable).

Botones y popups OWL para cr��dito.

Dependencias: point_of_sale, custom_credit_mooch.

:shopping_bags: custom_purchase_mooch

Descripci��n: Mejoras al flujo de compras.

Caracter��sticas:

Descuento global en ��rdenes de compra.

Validaci��n de presupuesto por departamento.

Wizard de selecci��n m��ltiple de productos.

Dependencias: purchase, account.

:bar_chart: custom_reports_mooch

Descripci��n: Reportes personalizados y plantillas QWeb.

Caracter��sticas:

Reporte de Orden de Compra con campos adicionales.

Reportes de termopanel con m��tricas.

Dependencias: report, purchase.

:package: custom_stock_mooch

Descripci��n: Extensi��n de gesti��n de inventario.

Caracter��sticas:

Segmentaci��n de pickings por evento.

Devoluciones mejoradas con selecci��n de l��neas.

Dependencias: stock, custom_purchase_mooch.

:wrench: product_mooch

Descripci��n: L��gica de negocio para productos.

Caracter��sticas:

C��lculo de m��rgenes y precios.

Generaci��n de c��digos internos.

Gesti��n de atributos (departamento, tipo, color, talla).

Dependencias: product, barcode.

:book: Uso B��sico

Configura par��metros en Ajustes �� Par��metros.

Navega a los men��s (Ventas, Compras, Inventario, POS, Reportes).

Prueba las funcionalidades y consulta logs en nivel DEBUG si es necesario.

:handshake: Contribuciones

?Bienvenides! Para aportar:

git clone git@github.com:AdrianHernandezMooch/mooch-custom-addons.git
cd mooch-custom-addons
git checkout -b feature/mi-cambio
# Realiza cambios, a?ade tests, documenta
git push origin feature/mi-cambio

Luego abre un Pull Request describiendo tu mejora.

:memo: Licencia

Distribuido bajo la Licencia MIT. Consulta LICENSE para m��s detalles.

