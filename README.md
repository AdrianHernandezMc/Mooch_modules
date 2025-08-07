Mooch Custom Odoo Modules

Este repositorio agrupa una serie de módulos personalizados desarrollados para Odoo 17/18 bajo la marca Mooch. Cada módulo extiende o mejora funcionalidades estándar de Odoo en áreas de conexión SQL, gestión de crédito, Punto de Venta, compras, reportes, inventario y productos.

Tabla de Contenidos

Requisitos

Instalación

Visión General de Módulos

conection_sql_mooch

custom_credit_mooch

custom_point_of_sale_mooch

custom_purchase_mooch

custom_reports_mooch

custom_stock_mooch

product_mooch

Uso Básico

Contribuciones

Licencia

Requisitos

Odoo versión 17 o 18

Python 3.10+

Dependencias mínimas (instaladas en tu entorno virtual de Odoo):

psycopg2

reportlab

html2canvas, jsPDF (para exportar organigramas)

Otras dependencias propias de Odoo (ver requirements.txt de Odoo)

Instalación

Clona este repositorio en tu carpeta de módulos de Odoo:

cd /ruta/a/tu/odoo/custom_addons
git clone git@github.com:AdrianHernandezMooch/mooch-custom-addons.git

Asegúrate de que el directorio aparezca en la configuración de Odoo (addons_path).

Mooch Custom Odoo Modules

Este repositorio agrupa una serie de módulos personalizados desarrollados para Odoo 17/18 bajo la marca Mooch. Cada módulo extiende o mejora funcionalidades estándar de Odoo en áreas de conexión SQL, gestión de crédito, Punto de Venta, compras, reportes, inventario y productos.

Tabla de Contenidos

Requisitos

Instalación

Visión General de Módulos

conection_sql_mooch

custom_credit_mooch

custom_point_of_sale_mooch

custom_purchase_mooch

custom_reports_mooch

custom_stock_mooch

product_mooch

Uso Básico

Contribuciones

Licencia

Requisitos

Odoo versión 17 o 18

Python 3.10+

Dependencias mínimas (instaladas en tu entorno virtual de Odoo):

psycopg2

reportlab

html2canvas, jsPDF (para exportar organigramas)

Otras dependencias propias de Odoo (ver requirements.txt de Odoo)

Instalación

Clona este repositorio en tu carpeta de módulos de Odoo:

cd /ruta/a/tu/odoo/custom_addons
git clone git@github.com:AdrianHernandezMooch/mooch-custom-addons.git

Asegúrate de que el directorio aparezca en la configuración de Odoo (addons_path).

Reinicia el servicio de Odoo:

sudo systemctl restart odoo

Actualiza la lista de Apps en la interfaz de Odoo, activa el modo Desarrollador y busca cada módulo por su nombre técnico.

Instala los módulos en el orden de sus dependencias (si aplica).

Visión General de Módulos

conection_sql_mooch

Descripción: Facilita conexiones directas a bases de datos externas vía SQL.

Características:

Configuración de parámetros de conexión (host, port, user, password, dbname).

Métodos para ejecutar consultas y volcar resultados en modelos Odoo.

Dependencias: Ninguna (usa la biblioteca estándar de Python).

custom_credit_mooch

Descripción: Añade gestión de precio y ventas a crédito.

Características:

Campo credit_price en product.template.

Integración en ventas normales y Punto de Venta.

Reportes de cuentas por cobrar.

Dependencias: sale.

custom_point_of_sale_mooch

Descripción: Personalizaciones para el Punto de Venta de Odoo.

Características:

Funcionalidad de devolución de productos desde el POS.

Alertas cuando el efectivo en caja supera un umbral configurable.

Botones y popups OWL para gestionar crédito desde el POS.

Dependencias: point_of_sale, custom_credit_mooch.

custom_purchase_mooch

Descripción: Mejoras al flujo de compras de Odoo.

Características:

Descuento global en órdenes de compra.

Validación de presupuesto por departamento.

Wizard de selección múltiple de productos para líneas de OC.

Dependencias: purchase, account.

custom_reports_mooch

Descripción: Reportes personalizados y plantillas QWeb.

Características:

Nuevo reporte de Orden de Compra con campos adicionales.

Reportes de termopanel con métricas y etiquetas.

Dependencias: report, purchase.

custom_stock_mooch

Descripción: Extiende la gestión de inventario.

Características:

Segmentación de pickings por evento/entrada.

Formulario de devolución de stock mejorado con selección de líneas.

Dependencias: stock, custom_purchase_mooch.

product_mooch

Descripción: Lógica de negocio para productos.

Características:

Cálculo automático de márgenes y precios de venta.

Generación automática de códigos internos.

Gestión de atributos (departamento, tipo, color, talla).

Dependencias: product, barcode.

Uso Básico

Tras la instalación, configura los parámetros en Ajustes → Parámetros según el módulo (por ejemplo, umbral de efectivo, porcentajes de descuento, conexiones SQL, etc.).

Navega al menú correspondiente (Ventas, Compras, Inventario, POS, Reportes) y prueba las nuevas funcionalidades.

Para desarrollo y debugging, habilita los logs de nivel INFO/DEBUG en el archivo de configuración de Odoo.

Contribuciones

¡Las contribuciones son bienvenidas! Para mejoras, bugs o nuevas funcionalidades:

Haz fork de este repositorio.

Crea una feature branch: git checkout -b feature/mi-nueva-funcionalidad.

Realiza tus cambios, añade tests y documentación.

Envía tu pull request detallando el cambio.

Licencia

Este proyecto se distribuye bajo la Licencia MIT. Consulta el archivo LICENSE para más detalles.
