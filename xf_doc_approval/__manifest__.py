# -*- coding: utf-8 -*-
{
    'name': 'Document Approval Workflow',
    'version': '1.0.2',
    'summary': """
    Dynamic, Customizable and Flexible approval process for documents
    | electronic document approval 
    | online document approval process
    | doc approval cycle 
    | doc approval process
    | document approval workflow
    | approve document package
    | document approval system
    | approve doc package
    | contract approval process
    | invoice approval process
    """,
    'category': 'Document Management',
    'author': 'XFanis',
    'support': 'xfanis.dev@gmail.com',
    'website': 'https://xfanis.dev/odoo.html',
    'license': 'OPL-1',
    'price': 25,
    'currency': 'EUR',
    'description':
        """
Document Approval Cycle
=======================
This module helps to create multiple custom, flexible and dynamic approval route
for any type of documents based on settings.

Key Features:

 * Any user can initiate unlimited approval process for documents
 * Pre-defined team of approvers or custom flow specified by the initiator
 * Parallel or serial (step-by-step) approval route for documents
 * Multi-level approval workflow for document packages
 * Documents approval by button or by "handwritten" signature (using mouse or touchscreen)
 * Multi Company features of Odoo System are supported
 
        """,
    'data': [
        # Access
        'security/security.xml',
        'security/ir.model.access.csv',
        # Views
        'views/menuitems.xml',
        'views/team.xml',
        'views/document_package.xml',
        'views/department_view.xml',
        'views/approver_wizard.xml',
        'views/formate_view.xml',
        'views/doc_dashboard.xml',

        # Data
        'data/mail_templates.xml',
        'data/data.xml',
        'data/mail_message_subtypes.xml',

    ],
    'depends': ['base', 'web', 'mail', 'hr', 'board','global_translation'],
    'images': [
        'static/description/xf_doc_approval.png',
    ],
    'assets': {
        'web.assets_backend': [
            'xf_doc_approval/static/src/css/custom_styles.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}
