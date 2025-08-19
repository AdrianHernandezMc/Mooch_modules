{
    'name': 'Custom Reports Moooch',
    'version': '17.0.1.0.0',
    'author': ['Adrian Hernandez'],
    'category': 'Reporting',
    'summary': 'Añade campos extra a los informes de Ventas y Compras',
    'license': 'Other proprietary',
    'depends': ['sale', 'purchase','hr','hr_attendance','hr_biometric_attendance'],
    'data': [
        'views/report_purchaseorder_custom.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}