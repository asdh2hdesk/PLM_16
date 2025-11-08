{
    'name': 'PLM Version Diff',
    'version': '16.0.1.0.0',
    'author': 'Megha',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'mrp'],
    'data': [
        'security/ir.model.access.csv',
        'views/version_diff_views.xml',
        'views/version_diff_menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}