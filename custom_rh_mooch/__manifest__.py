# custom_rh_mooch/__manifest__.py
{
    "name": "Custom RH Mooch",
    "version": "17.0.1.0.0",
    'category': 'RH',
    "summary": "Cambios, campos y actualizaciones personalizadas para el modulo de recursos humanos.",
    'author': 'Adrian Hernandez',
    "depends": ["hr","custom_reports_mooch"],
    "data": [
        "views/hr_employee_views.xml",
    ],
    "installable": True,
    "application": False,
}
