# __manifest__.py
{
    'name': 'Supplier Document Workflow',
    'version': '16.0.1.0.0',
    'author': 'Megha',
    'category': 'Document Management',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/vendor_document_views.xml',
    ],
    'installable': True,
    'application': True,
}