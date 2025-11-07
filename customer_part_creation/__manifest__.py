# -*- coding: utf-8 -*-
{
    'name': 'Part Creation',
    'version': '16.0.1.0',
    'category': 'Quality',
    'summary': 'ISO Document & Drawing Control | Document Control Process (ISO 9001:2015 – Clause 7.5.3)',
    'description': """
        Comprehensive Document Control System with ISO 9001:2015 Compliance
        Manages drawing revisions, approvals, and document lifecycle
    """,
    'author': 'Akshat Gupta',
    'price': 120.0,
    'currency': "USD",
    'license': 'LGPL-3',
    'sequence': 1,
    'website': 'https://github.com/Akshat-10',
    'support': 'akshat.gupta10m@gmail.com',
    'maintainer': 'Akshat Gupta',
    'depends': ['base', 'mail', 'product'],

    'data': [
        'security/document_security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/mail_template.xml',
        'data/default_approval_config.xml',
        'views/menu.xml',
        'views/drawing_views.xml',
        'views/revision_views.xml',
        'views/document_approval_config_views.xml',
        'views/product_template_view.xml',
    ],
    
    
    'installable': True,
    'auto_install': False,
    'application': True,
}
