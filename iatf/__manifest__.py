{
    'name': 'IATF',
    'version': '16.0.1.0',
    'category': 'Custom',
    'summary': '',
    'description': "QMS Documents",
    'author': 'ASD',
    'license': 'LGPL-3',
    'sequence': 1,
    'currency': "INR",
    'website': 'https://asdsoftwares.com/',
    'depends': ['hr', 'base','product','mail','global_translation',],
    'data': [
        'security/ir.model.access.csv',
        # 'data/data.xml',
        'views/menu_items.xml',
        'views/iatf_sign_off_members.xml',
        'views/advanced_revision_views.xml',
    ],
    'assets':{
        'web.assets_backend': [
            'iatf/static/src/css/custom.css',

        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}
