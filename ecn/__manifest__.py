{
    'name': 'engineering_change_note',
    'version': '16.0.1.0',
    'category': 'Custom',
    'summary': '',
    'description': """""",
    'author': 'ASD',
    'price': 0,
    'license': 'LGPL-3',
    'sequence': 1,
    'currency': "INR",
    'website': 'https://asdsoftwares.com/',
    'depends': ['hr', 'base', 'sale', 'mrp', 'product', 'maintenance', 'crm', 'project', 'l10n_in','board','web','global_translation','customer_part_creation'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_ecn_template.xml',
        'views/ecn_view.xml',
        'views/document_control_inherit.xml',

    ],


    'installable': True,
    'auto_install': False,
    'application': True,
}
