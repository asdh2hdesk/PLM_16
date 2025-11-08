from odoo import models, fields, api
from odoo.exceptions import UserError


class VendorDocument(models.Model):
    _name = 'vendor.document'
    _description = 'Vendor Document Workflow'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Document Name', tracking=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor Name', domain="[('is_company', '=', True)]", tracking=True)
    vendor_code = fields.Char(string='Vendor Code', related='vendor_id.ref', store=True, tracking=True)
    responsible_user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user, tracking=True)
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

    attachment_file = fields.Binary(string='Attachment')
    attachment_filename = fields.Char(string='Filename')
    approver_ids = fields.Many2many('res.users', string='Approvers')

    # Overall approval status (computed)
    approval_status = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Overall Status', compute='_compute_approval_status', store=True)

    approval_date = fields.Date(string='Approval Date')
    remarks = fields.Text(string='Remarks')

    # One2many for individual approvals
    individual_approval_ids = fields.One2many(
        'vendor.document.approval',
        'document_line_id',
        string='Individual Approvals'
    )

    # Computed field to check if current user can approve
    can_current_user_approve = fields.Boolean(
        string='Can Approve',
        compute='_compute_can_current_user_approve'
    )

    @api.depends()
    def _compute_sr_no_1(self):
        """Automatically assign serial numbers based on record order"""
        for index, record in enumerate(self, start=1):
            record.sr_no_1 = index

    @api.depends('individual_approval_ids.status', 'approver_ids')
    def _compute_approval_status(self):
        """
        Compute overall approval status based on individual approvals:
        - pending: by default when no approvals exist OR all approvals are pending
        - rejected: if any approval is rejected
        - approved: if ALL approvers have approved
        - in_progress: if some have approved/rejected but not all
        """
        for record in self:
            # If no approvers assigned, status is pending
            if not record.approver_ids:
                record.approval_status = 'pending'
                record.approval_date = False
                continue

            # Get all individual approval statuses
            individual_approvals = record.individual_approval_ids

            # If no individual approvals created yet, status is pending
            if not individual_approvals:
                record.approval_status = 'pending'
                record.approval_date = False
                continue

            statuses = individual_approvals.mapped('status')
            total_approvers = len(record.approver_ids)
            total_approvals = len(individual_approvals)

            # If any rejection exists, overall status is rejected
            if 'rejected' in statuses:
                record.approval_status = 'rejected'
                record.approval_date = False

            # If all approvers have approved (count matches and all are approved)
            elif total_approvals == total_approvers and all(status == 'approved' for status in statuses):
                record.approval_status = 'approved'
                record.approval_date = fields.Date.today()

            # If some approvals exist but not all approvers have responded, it's in progress
            elif total_approvals > 0 and total_approvals < total_approvers:
                record.approval_status = 'in_progress'
                record.approval_date = False

            # If some have approved but some are pending (mixed state), it's in progress
            elif 'approved' in statuses and 'pending' in statuses:
                record.approval_status = 'in_progress'
                record.approval_date = False

            # If all statuses are 'pending', overall status is pending
            else:
                record.approval_status = 'pending'
                record.approval_date = False

    @api.depends('approver_ids', 'individual_approval_ids.user_id')
    def _compute_can_current_user_approve(self):
        """Check if current user is in approvers and hasn't approved yet"""
        current_user = self.env.user
        for record in self:
            if current_user in record.approver_ids:
                existing_approval = record.individual_approval_ids.filtered(
                    lambda a: a.user_id == current_user
                )
                record.can_current_user_approve = not existing_approval
            else:
                record.can_current_user_approve = False

    @api.onchange('approver_ids')
    def _onchange_approver_ids(self):
        """Create individual approval records when approvers are added"""
        if self.approver_ids:
            # Get existing approval user IDs
            existing_user_ids = self.individual_approval_ids.mapped('user_id')

            # Create approvals for new users
            new_approvers = self.approver_ids - existing_user_ids
            for user in new_approvers:
                self.individual_approval_ids = [(0, 0, {
                    'user_id': user.id,
                    'status': 'pending'
                })]

            # Remove approvals for users no longer in approver_ids
            removed_approvals = self.individual_approval_ids.filtered(
                lambda a: a.user_id not in self.approver_ids
            )
            if removed_approvals:
                self.individual_approval_ids = [(2, approval.id) for approval in removed_approvals]

    def action_approve(self):
        """Current user approves this document line"""
        self.ensure_one()
        current_user = self.env.user

        if current_user not in self.approver_ids:
            raise UserError("You are not authorized to approve this document.")

        # Check if user already approved
        existing_approval = self.individual_approval_ids.filtered(
            lambda a: a.user_id == current_user
        )

        if existing_approval:
            raise UserError("You have already submitted your approval for this document.")

        # Create approval record
        self.env['vendor.document.approval'].create({
            'document_line_id': self.id,
            'user_id': current_user.id,
            'status': 'approved',
            'approval_date': fields.Date.today(),
        })

        # Log in chatter
        self.document_id.message_post(
            body=f"Document line {self.sr_no_1} approved by {current_user.name}",
            subject="Document Approved"
        )

    def action_reject(self):
        """Current user rejects this document line"""
        self.ensure_one()
        current_user = self.env.user

        if current_user not in self.approver_ids:
            raise UserError("You are not authorized to reject this document.")

        # Check if user already submitted approval/rejection
        existing_approval = self.individual_approval_ids.filtered(
            lambda a: a.user_id == current_user
        )

        if existing_approval:
            raise UserError("You have already submitted your decision for this document.")

        # Open wizard for rejection remarks
        return {
            'name': 'Reject Document',
            'type': 'ir.actions.act_window',
            'res_model': 'vendor.document.rejection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_document_line_id': self.id,
            }
        }


class VendorDocumentApproval(models.Model):
    _name = 'vendor.document.approval'
    _description = 'Individual Document Approval'
    _order = 'approval_date desc, id desc'

    document_line_id = fields.Many2one(
        'vendor.document.line',
        string='Document Line',
        required=True,
        ondelete='cascade'
    )
    user_id = fields.Many2one('res.users', string='Approver', required=True)
    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', required=True)
    approval_date = fields.Date(string='Decision Date')
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('unique_user_document',
         'unique(document_line_id, user_id)',
         'Each user can only approve once per document line!')
    ]


class VendorDocumentRejectionWizard(models.TransientModel):
    _name = 'vendor.document.rejection.wizard'
    _description = 'Document Rejection Wizard'

    document_line_id = fields.Many2one('vendor.document.line', string='Document Line', required=True)
    remarks = fields.Text(string='Rejection Remarks', required=True)

    def action_confirm_reject(self):
        """Confirm rejection with remarks"""
        self.ensure_one()
        current_user = self.env.user

        # Create rejection record
        self.env['vendor.document.approval'].create({
            'document_line_id': self.document_line_id.id,
            'user_id': current_user.id,
            'status': 'rejected',
            'approval_date': fields.Date.today(),
            'remarks': self.remarks,
        })

        # Log in chatter
        self.document_line_id.document_id.message_post(
            body=f"Document line {self.document_line_id.sr_no_1} rejected by {current_user.name}. Reason: {self.remarks}",
            subject="Document Rejected"
        )

        return {'type': 'ir.actions.act_window_close'}
