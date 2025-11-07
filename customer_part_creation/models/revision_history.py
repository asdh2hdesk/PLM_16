from odoo import models, fields, api
from odoo.exceptions import UserError

class DocumentRevision(models.Model):
    _name = 'document.revision'
    _inherit = ['mail.thread', 'mail.activity.mixin',"translation.mixin"]
    _description = 'Document Revision History'
    _rec_name = 'revision_number'
    _order = 'revision_date desc'
    
    revision_date = fields.Date(string='Date of Modification', default=fields.Date.today)
    revision_number = fields.Char(string='Revision No.', required=True)
    revision_description = fields.Char(string='Revision Description',translate=True)
    modified_by = fields.Many2one('res.users', string='Modification By', default=lambda self: self.env.user)
    approved_by = fields.Many2one('res.users', string='Modification Approved By')
    date_approved = fields.Date(string='Date of Modification Approved')
    document_id = fields.Many2one('document.control', string='Document', required=True)
    # Modified: Made previous_revision_ids read-only to prevent direct creation
    previous_revision_ids = fields.Many2many(
        'document.revision',
        relation='document_revision_previous_revision_rel',
        column1='current_revision_id',
        column2='previous_revision_id',
        string='Previous Revisions',
        # domain="[('document_id', '=', document_id)]"
    )
    release_to = fields.Many2many('res.users', string='Release To')
    previous_revision_drawings = fields.Html(string='Modified Revision Drawings',translate=True)
    obsolete_date = fields.Date(string='Obsolete Date', readonly=True)
    drawing_file = fields.Binary(string='Revised Drawing', attachment=True)
    drawing_file_filename = fields.Char(string='Drawing Filename')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('released', 'Released'),
        ('cancled', 'Cancled'),
    ], string='Status', default='draft', tracking=True)
    approved_by_users = fields.Many2many(
        'res.users',
        relation='revision_approved_by_rel',
        string='Approved By'
    )
    to_be_approved_by_users = fields.Many2many(
        'res.users',
        relation='revision_to_be_approved_by_rel',
        string='To Be Approved By'
    )

    @api.model
    def create(self, vals):
        # Check if there is any existing revision not in 'released' state for this document
        if 'document_id' in vals:
            document = self.env['document.control'].browse(vals['document_id'])
            for revision in document.revision_ids:
                if revision.state != 'released':
                    raise UserError("You cannot create a new revision while another revision is not in the 'released' state.")
        
        # Set approvers from config when creating
        config = self.env['document.approval.config'].search([], limit=1)
        if config:
            vals['to_be_approved_by_users'] = [(6, 0, config.approver_ids.ids)]
        else:
            vals['to_be_approved_by_users'] = [(6, 0, [])]
        res = super(DocumentRevision, self).create(vals)
        # Trigger recomputation of parent document fields
        if res.document_id:
            res.document_id._compute_current_revision()
        return res

    def action_request_approval(self):
        self.ensure_one()
        self.write({
            'state': 'pending_approval',
            'approved_by_users': [(5, 0, 0)]  # Clear any previous approvals
        })

    def action_approve(self):
        self.ensure_one()
        # Check if user has approver or manager rights
        if not (self.env.user.has_group('customer_part_creation.group_document_approver')):
            raise UserError("You don't have permission to approve revisions.")
        if self.env.user not in self.to_be_approved_by_users:
            raise UserError("You are not authorized to approve this revision.")
        if self.env.user in self.approved_by_users:
            raise UserError("You have already approved this revision.")
        self.write({'approved_by_users': [(4, self.env.user.id)]})
        # Check if all approvers have approved
        if all(approver in self.approved_by_users for approver in self.to_be_approved_by_users):
            self.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'date_approved': fields.Date.today()
            })

    # Modified: Added notification logic to action_release_revision
    def action_release_revision(self):
        self.ensure_one()
        self.write({
            'state': 'released',
            'obsolete_date': fields.Date.today()
        })
        template = self.env.ref('customer_part_creation.email_template_revision_released')
        for user in self.release_to:
            if user.email:
                email_values = {'email_to': user.email}
                context = {'recipient_user': user}
                template.with_context(**context).send_mail(self.id, force_send=True, email_values=email_values)
    
    def action_undo(self):
        self.ensure_one()
        state_map = {
            'pending_approval': 'draft',
            'approved': 'pending_approval',
            'released': 'approved',
            'cancled': 'draft'
        }
        if self.state in state_map:
            self.write({'state': state_map[self.state]})
            
    def action_cancel(self):
        self.ensure_one()
        self.write({'state': 'cancled'})
    
    def write(self, vals):
        res = super(DocumentRevision, self).write(vals)
        # If revision_description is updated, trigger recomputation
        if 'revision_description' in vals:
            for record in self:
                if record.document_id:
                    record.document_id._compute_current_revision()
        return res
