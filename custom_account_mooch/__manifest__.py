# custom_account_mooch/__manifest__.py
{
    'name': 'Custom Contabilidad Mooch', # O 'Account Transfer Ref'
    'version': '17.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Agrega número de transferencia a facturas (account.move)',
    'author': 'Adrian Hernandez',
    'depends': ['base', 'account'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
}