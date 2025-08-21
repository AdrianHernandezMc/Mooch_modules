{
    'name': 'Custom Reports Moooch',
    'version': '17.0.1.0.0',
    'author': ['Adrian Hernandez'],
    'category': 'Reporting',
    'summary': 'Añade campos extra a los informes de Ventas y Compras',
    'license': 'Other proprietary',
    'depends': ['sale', 'purchase','hr','hr_attendance','hr_biometric_attendance','custom_rh_mooch'],
    'data': [
        # Security
        'security/ir.model.access.csv',
        # Compras
        'views/report_purchaseorder_custom.xml',
        # Asistencias
        'views/attendance_report_actions.xml',
        'views/attendance_report_templates.xml',
        'views/attendance_report_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}