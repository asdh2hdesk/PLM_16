# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from .selection import ApproverState, ApprovalMethods, ApprovalStep

class DocApprovalTeamLines(models.Model):
    _name = 'xf.doc.approval.team.lines'
    _description = 'Doc Approval Team Lines'

    doc_approval_team_id = fields.Many2one('xf.doc.approval.team')

    risk_assessment_id = fields.Many2one('risk.assessment')
    is_risk_assessment = fields.Boolean('Allowed')

    things_right_wrong_id = fields.Many2one('things.wrong.right')
    is_things_right_wrong = fields.Boolean('Allowed')

class DocApprovalTeam(models.Model):
    _name = 'xf.doc.approval.team'
    _description = 'Doc Approval Team'
    _inherit = "translation.mixin"

    doc_approval_team_line_ids = fields.One2many(string='Documents',
                                                 comodel_name='xf.doc.approval.team.lines',
                                                 inverse_name='doc_approval_team_id')

    active = fields.Boolean('Active', default=True)

    name = fields.Char(
        string='Project Name',
        required=True,translate=True
    )
    user_id = fields.Many2one(
        string='Team Leader',
        comodel_name='res.users',
        required=True,
        default=lambda self: self.env.user,
        index=True
    )
    company_id = fields.Many2one(
        string='Company',
        comodel_name='res.company',
        required=True,
        default=lambda self: self.env.company.id,
        index=True,
    )
    approver_ids = fields.One2many(
        string='Approvers',
        comodel_name='xf.doc.approval.team.approver',
        inverse_name='team_id',
    )
    start_date = fields.Date('Start Date')
    stop_date = fields.Date('Stop Date')

    tgt_start_date = fields.Date('Target Start Date')
    tgt_stop_date = fields.Date('Target Stop Date')
    project_num = fields.Char('Project Num.',translate=True)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('complete', 'Completed'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft')
    # Validation

    @api.constrains('company_id')
    def _check_team_company(self):
        for team in self:
            team.approver_ids.validate_company(team.company_id)


class DocApprovalApproverAbstract(models.Model):
    _name = 'xf.doc.approval.approver.abstract'
    _description = 'Abstract Approver'
    _order = 'step'
    _rec_name = 'user_id'
    step = fields.Selection(
        string='Step',
        selection=ApprovalStep.list,
        required=True,
        default=ApprovalStep.default,
    )
    user_id = fields.Many2one(
        string='Approver',
        comodel_name='res.users',
        required=True
    )
    role = fields.Char(
        string='Role/Position',
        required=True,
        default="Approver"
    )

    # Onchange handlers

    @api.onchange('user_id')
    def _detect_user_role(self):
        for approver in self:
            # if user related to employee, try to get job title for hr.employee
            employee = hasattr(approver.user_id, 'employee_ids') and getattr(approver.user_id, 'employee_ids')
            employee_job_id = hasattr(employee, 'job_id') and getattr(employee, 'job_id')
            employee_job_title = employee_job_id.name if employee_job_id else False
            if employee_job_title:
                approver.role = employee_job_title
                continue
            # if user related partner, try to get job title for res.partner
            partner = approver.user_id.partner_id
            partner_job_title = hasattr(partner, 'function') and getattr(partner, 'function')
            if partner_job_title:
                approver.role = partner_job_title

    # Validation

    @api.constrains('user_id')
    def _check_users(self):
        for approver in self:
            if not approver.user_id.has_group('xf_doc_approval.group_xf_doc_approval_user'):
                raise ValidationError(_('%s does not have access to the Doc Approval module.') % (approver.user_id.name,)
                                      + '\n' +
                                      _('Please ask system administrator to add him/her to the Doc Approval module group first.'))

    def validate_company(self, company):
        if not company:
            return
        for approver in self:
            if company not in approver.user_id.company_ids:
                raise ValidationError(
                    _('%s does not have access to the company %s') % (approver.user_id.name, company.name))


class DocApprovalTeamApprover(models.Model):
    _name = 'xf.doc.approval.team.approver'
    _inherit = ['xf.doc.approval.approver.abstract']
    _description = 'Approval Team Member'

    team_id = fields.Many2one(
        string='Team',
        comodel_name='xf.doc.approval.team',
        required=True,
        ondelete='cascade'
    )

    # Validation

    @api.constrains('user_id', 'team_id')
    def _check_users(self):
        for approver in self:
            approver.validate_company(approver.team_id.company_id)
        return super(DocApprovalTeamApprover, self)._check_users()


class DocApprovalDocumentApprover(models.Model):
    _name = 'xf.doc.approval.document.approver'
    _inherit = ['xf.doc.approval.approver.abstract', "translation.mixin"]
    _description = 'Doc Approver'

    team_approver_id = fields.Many2one(
        string='Doc Team Approver',
        comodel_name='xf.doc.approval.team.approver',
        ondelete='set null'
    )
    document_package_id = fields.Many2one(
        string='Document Package',
        comodel_name='xf.doc.approval.document.package',
        required=True,
        ondelete='cascade',
    )
    method = fields.Selection(
        string='Method',
        selection=ApprovalMethods.list,
        related='document_package_id.method',
        readonly=True,
    )
    state = fields.Selection(
        string='Status',
        selection=ApproverState.list,
        readonly=True,
        required=True,
        default=ApproverState.default
    )
    notes = fields.Text(
        string='Notes',
        readonly=True,
        translate=True
    )

    # Validation

    @api.constrains('user_id', 'document_package_id')
    def _check_users(self):
        for approver in self:
            approver.validate_company(approver.document_package_id.company_id)
        return super(DocApprovalDocumentApprover, self)._check_users()

    # User actions

    def action_wizard(self, view_ref, window_title):
        self.ensure_one()
        view = self.env.ref('xf_doc_approval.' + view_ref)
        return {
            'name': window_title,
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new'
        }

    def action_approve(self):
        for approver in self:
            document_package = approver.document_package_id
            approver.state = 'approved'
            if document_package.approval_state == 'to approve':
                document_package.sudo().action_send_for_approval()
            elif document_package.approval_state == 'approved':
                document_package.sudo().action_finish_approval()

    def action_reject(self):
        for approver in self:
            approver.state = 'rejected'
            approver.document_package_id.sudo().set_state('rejected', {'reject_reason': approver.notes})
