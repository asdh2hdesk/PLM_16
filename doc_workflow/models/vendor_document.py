from odoo import models, fields, api


class VendorDocument(models.Model):
    _name = 'vendor.document'
    _description = 'Vendor Document Workflow'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Document Name', tracking=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor',
                                domain=[('supplier_rank', '>', 0)], tracking=True)
    submission_date = fields.Date(string='Submission Date', default=fields.Date.today, tracking=True)

    state = fields.Selection([
        ('submitted', 'Vendor Document Submission'),
        ('quality_review', 'Quality Review'),
        ('approval', 'Approval'),
        ('integrated', 'Integration into Project Documentation')
    ], string='Stage', default='submitted', tracking=True)

    notes = fields.Text(string='Notes')

    # One2many field for document lines
    document_line_ids = fields.One2many('vendor.document.line', 'document_id', string='Document Lines')

    def action_quality_review(self):
        self.state = 'quality_review'

    def action_approval(self):
        self.state = 'approval'

    def action_integrate(self):
        self.state = 'integrated'


class VendorDocumentLine(models.Model):
    _name = 'vendor.document.line'
    _description = 'Vendor Document Line'
    _order = 'sequence, id'

    document_id = fields.Many2one('vendor.document', string='Document', ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    sr_no_1 = fields.Integer(string='Serial Number', compute='_compute_sr_no_1', store=False)

    @api.depends()
    def _compute_sr_no_1(self):
        """Automatically assign serial numbers based on record order"""
        for index, record in enumerate(self, start=1):
            record.sr_no_1 = index
    document_format = fields.Selection([
        ('pdf', 'PDF'),
        ('doc', 'DOC/DOCX'),
        ('xls', 'XLS/XLSX'),
        ('dwg', 'DWG'),
        ('jpg', 'JPG/PNG'),
        ('other', 'Other')
    ], string='Format', required=True)
    attachment_file = fields.Binary(string='Attachment')
    attachment_filename = fields.Char(string='Filename')
    approver_id = fields.Many2one('res.users', string='Approver', required=True)
    approval_status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending')
    approval_date = fields.Date(string='Approval Date')
    remarks = fields.Text(string='Remarks')