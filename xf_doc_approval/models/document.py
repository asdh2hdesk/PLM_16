from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
from .selection import ApprovalMethods, DocumentState, ApproverStateUpdated, ApprovalStep, DocumentVisibility
from datetime import date, datetime
import logging
_logger = logging.getLogger(__name__)

_editable_states = {
    False: [('readonly', False)],
    'draft': [('readonly', False)],
}


class HrDeptType(models.Model):
    _name = 'hr.dept.type'

    name = fields.Char("Department Type")

    @api.depends('name')
    def name_get(self):
        res = []
        for record in self:
            name = record.name
            res.append((record.id, name))
        return res

class ProductTemplateInherited(models.Model):
    _inherit = "product.template"

    customer_part_creation_id = fields.Many2one('customer.part.creation', 'Customer part id')
    drg_no = fields.Char("Drawing Number.")
    drg_revision_no = fields.Char("Drawing Revision No.")
    drg_revision_date = fields.Date("Drawing Revision Date")

    customer_id = fields.Many2one('res.partner','Customer Name')
    customer_part_name = fields.Char('Customer Part Name')
    customer_part_no = fields.Char('Customer Part No.')

class HrDepartment(models.Model):
    _inherit = 'hr.department'

    department_type = fields.Many2one('hr.dept.type', 'Department Type')

class DocApprovalDocumentPackage(models.Model):
    _name = 'xf.doc.approval.document.package'
    _inherit = ['mail.thread']
    _description = 'Document Package'
    _rec_name = 'name'

    active = fields.Boolean(default=True)
    name = fields.Char(
        string='Project Name',
        required=True,
        readonly=True,
        states=_editable_states,
        tracking=True,
    )
    used_in_project_type_id = fields.Many2one(comodel_name='doc.project.type',string='Project type')
    partner_id = fields.Many2one('res.partner', string='Customer Name')
    start_date = fields.Date('Start Date', default=date.today())
    target_date = fields.Date('Target Date')
    project_start_date = fields.Date('Project Start Date', compute='_compute_date')
    project_end_date = fields.Date('Project End Date', compute='_compute_date')
    doc_type = fields.Selection([('safelaunch', 'Safe Launch'), ('prototype', 'Prototype'), ('prelaunch', 'PreLaunch'),
                             ('production', 'Production')])
    part_id = fields.Many2one("product.template", string="Part")
    part_name = fields.Char("Part Name", related="part_id.name")
    part_number = fields.Char("Part Number", related="part_id.default_code")
    drawing_no = fields.Char("Drawing No.", related="part_id.drg_no")
    drawing_rev_no = fields.Char("Drawing. Rev. No.", related="part_id.drg_revision_no")
    drawing_rev_date = fields.Date("Drawing Rev. Date", related="part_id.drg_revision_date")
    # part_description = fields.Text("Part Description")
    description = fields.Text(
        string='Description',
        translate=True,
    )
    state = fields.Selection(
        string='Status',
        selection=DocumentState.list,
        required=True,
        default=DocumentState.default,
        readonly=True,
        tracking=True,
        compute='_compute_state',
    )
    approval_state = fields.Selection(
        string='Approval Status',
        selection=ApproverStateUpdated.list,
        compute='_compute_approval_state',
    )
    approval_step = fields.Selection(
        string='Approval Step',
        selection=ApprovalStep.list,
        compute='_compute_approval_step',
    )
    method = fields.Selection(
        string='Approval Method',
        selection=ApprovalMethods.list,
        required=True,
        default=ApprovalMethods.default,
        readonly=True,
        states=_editable_states,
    )
    visibility = fields.Selection(
        string='Visibility',
        selection=DocumentVisibility.list,
        required=True,
        default=DocumentVisibility.default,
    )
    initiator_user_id = fields.Many2one(
        string='Initiator',
        comodel_name='res.users',
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        states=_editable_states,
    )
    company_id = fields.Many2one(
        string='Company',
        comodel_name='res.company',
        required=True,
        default=lambda self: self.env.company,
        readonly=True,
        states=_editable_states,
    )
    approval_team_id = fields.Many2one(
        string='Approval Team',
        comodel_name='xf.doc.approval.team',
        readonly=True,
        states=_editable_states,
        domain="[('company_id', '=', company_id)]",
    )
    approver_ids = fields.One2many(
        string='Approvers',
        comodel_name='xf.doc.approval.document.approver',
        inverse_name='document_package_id',
        readonly=True,
        states=_editable_states,
    )
    document_ids = fields.One2many(
        string='Documents',
        comodel_name='xf.doc.approval.document',
        inverse_name='document_package_id',
        readonly=True,
        states=_editable_states,
    )

    document_approval_ids = fields.One2many(
        string='Documents Approval',
        comodel_name='document.approval',
        inverse_name='document_package_id',
    )

    is_initiator = fields.Boolean('Is Initiator', compute='_compute_access')
    is_approver = fields.Boolean('Is Approver', compute='_compute_access')
    reject_reason = fields.Text('Reject Reason')
    is_select_all = fields.Boolean('Is Select All')
    check_sequence = fields.Boolean('Check Sequence', compute='_check_sequence')
    line_status = fields.Char('Format Status', compute='_compute_line_status')
    start_diff = fields.Char(string='Start Date Diff.', compute='_get_date_diff')
    end_diff = fields.Char(string='End Date Diff.', compute='_get_date_diff')

    # part_number = fields.Char("Part Number")
    # part_description = fields.Text("Part Description")
    # customer_part_name = fields.Char("Customer Part name")

    _sql_constraints = [('xf_document_project_name_unique', 'unique(name)', 'A project with this name already exists.')]
    def _get_date_diff(self):
        for rec in self:
            start_diff = " 0"
            end_diff = "0"
            if rec.project_start_date and rec.start_date:
                start_diff = (rec.project_start_date - rec.start_date).days
            if rec.project_end_date and rec.target_date:
                end_diff = (rec.project_end_date - rec.target_date).days

            rec.start_diff = str(start_diff) + ' Days'
            rec.end_diff = str(end_diff) + ' Days'

    def _compute_date(self):
        for rec in self:
            # Default to existing values
            project_start_date = rec.project_start_date
            project_end_date = rec.project_end_date

            # Safely filter on status
            approved_total = rec.document_approval_ids.filtered(
                lambda l: 'status' in l._fields and l.status != 'Draft'
            )
            approved_total2 = rec.document_approval_ids.filtered(
                lambda l: hasattr(l, 'status') and l.status not in ['Draft', 'Approval Inprogress']
            )

            if not project_end_date and len(approved_total2) == len(rec.document_approval_ids):
                rec.project_end_date = date.today()
            else:
                rec.project_end_date = project_end_date

    def _compute_state(self):
        for rec in self:
            current_staus_of_record = rec.document_approval_ids
            total = len(current_staus_of_record)
            revised = len(current_staus_of_record.filtered(lambda a: 'status' in a._fields and a.status == 'revision'))
            approved = len(current_staus_of_record.filtered(lambda a: 'status' in a._fields and a.status == 'approved'))

            if len(current_staus_of_record) == len(
                    current_staus_of_record.filtered(lambda a: 'status' in a._fields and a.status == 'draft')):
                rec.state = 'draft'
            elif total == approved or approved + revised == total:
                rec.state = 'approved'
            elif len(current_staus_of_record.filtered(lambda a: 'status' in a._fields and a.status == 'rejected')):
                rec.state = 'rejected'
            else:
                rec.state = 'inprogress'

    def _compute_line_status(self):
        for rec in self:
            total = len(rec.document_approval_ids)
            approved_total = len(rec.document_approval_ids.filtered(lambda l: 'status' in l._fields and l.status not in ['pending', 'draft']))
            rec.line_status = str(approved_total) + '/' + str(total)

    def _check_sequence(self):
        for rec in self:
            all_lines = rec.document_approval_ids.filtered(lambda l: 'status' in l._fields and l.status != 'approved').ids
            all_lines = self.env['document.approval'].search([('id', 'in', all_lines)], order='sr_no asc')
            if all_lines:
                all_lines = self.env['document.approval'].search([('id', 'in', all_lines.ids),('sr_no', '=', all_lines[0].mapped('sr_no'))])
                all_lines.write({'check_sequence': True})
                rec.check_sequence = True
            else:
                rec.check_sequence = False

    def select_all_formate(self):
        department_lst = []
        formate_ids = self.env['document.formate'].search([]).filtered(lambda f : self.used_in_project_type_id.id in f.used_in_project_type_ids.ids)
        for formate in formate_ids:
            for department in formate.department_ids:
                # manager = department.filtered(lambda l: not l.manager_id or not l.department_type or not l.manager_id.work_email)
                manager = department.filtered(lambda l: not l.manager_id or not l.manager_id.work_email)
                if manager:
                    if department.name not in department_lst:
                        department_lst.append(department.name)

        if department_lst:
            raise UserError(_('Please configure Deparment Manager and their Email Id\'s in following departments: \n\n  %s ', department_lst))
        self.is_select_all = True
        for rec in formate_ids:
            manager_ids = rec.department_ids.mapped('manager_id').ids
            vals = {
                'serial_no' : rec.serial_no,
                'sr_no' : rec.sr_no,
                'control_emp_ids' : [(6, 0, rec.control_emp_ids.ids)],
                'used_in_project_type_ids' : [(6, 0, rec.used_in_project_type_ids.ids)],
                'control_department_ids' : [(6, 0, rec.control_department_ids.ids)],
                'formate' : rec.id,
                'document_package_id' : self.id,
                'department_ids' : [(6, 0, rec.department_ids.ids)],
                'manager_ids' : [(6, 0, manager_ids)],
                }
            self.env['document.approval'].create(vals)

    # Compute fields

    @api.depends('state', 'approval_team_id')
    def _compute_access(self):
        for record in self:
            # Check if the current user is initiator (true for admin)
            record.is_initiator = self.env.user == record.initiator_user_id or self.env.user._is_admin()

            # Check if the document needs approval from current user (true for admin)
            current_approvers = record.get_current_approvers()
            responsible = self.env.user in current_approvers.mapped('user_id') or self.env.user._is_admin()
            record.is_approver = record.approval_state == 'pending' and responsible

    # @api.depends('approver_ids.state')
    # def _compute_approval_state(self):
    #     for record in self:
    #         approvers = record.approver_ids
    #         print(approvers)
    #         print(len(approvers))
    #         print(approvers.filtered(lambda a: a.state == 'approved'))
    #         if len(approvers) == len(approvers.filtered(lambda a: a.state == 'approved')):
    #             record.approval_state = 'approved'
    #         elif approvers.filtered(lambda a: a.state == 'rejected'):
    #             record.approval_state = 'rejected'
    #         elif approvers.filtered(lambda a: a.state == 'pending'):
    #             record.approval_state = 'pending'
    #         else:
    #             record.approval_state = 'to approve'

    @api.depends('document_approval_ids.status')
    def _compute_approval_state(self):
        for rec in self:
            current_staus_of_record = rec.document_approval_ids
            total = len(current_staus_of_record)
            revised = len(current_staus_of_record.filtered(lambda a: 'status' in a._fields and a.status == 'revision'))
            approved = len(current_staus_of_record.filtered(lambda a: 'status' in a._fields and a.status == 'approved'))

            if len(current_staus_of_record) == len(
                    current_staus_of_record.filtered(lambda a: 'status' in a._fields and a.status == 'draft')):
                rec.approval_state = 'Draft'
            elif total == approved or approved + revised == total:
                rec.approval_state = 'Approved'
            elif len(current_staus_of_record.filtered(lambda a: 'status' in a._fields and a.status == 'rejected')):
                rec.approval_state = 'Rejected'
            else:
                rec.approval_state = 'Approval Inprogress'

    @api.depends('approver_ids.state', 'approver_ids.step')
    def _compute_approval_step(self):
        for record in self:
            approval_step = None
            steps = record.approver_ids.mapped('step')
            steps.sort()
            for step in steps:
                if record.approver_ids.filtered(lambda a: a.step == step and a.state != 'approved'):
                    approval_step = step
                    break
            record.approval_step = approval_step

    # Onchange handlers

    @api.onchange('approval_team_id')
    def onchange_approval_team(self):
        if self.approval_team_id:

            team_approvers = []
            for team_approver in self.approval_team_id.approver_ids:
                team_approvers += [{
                    'step': team_approver.step,
                    'user_id': team_approver.user_id.id,
                    'role': team_approver.role,
                }]
            approvers = self.approver_ids.browse([])
            for a in team_approvers:
                approvers += approvers.new(a)
            self.approver_ids = approvers

    @api.onchange('approver_ids')
    def onchange_approvers(self):
        if self.approval_team_id:
            if self.approval_team_id.approver_ids.mapped('user_id') != self.approver_ids.mapped('user_id'):
                self.approval_team_id = None

    # Validation

    @api.constrains('company_id')
    def _validate_company(self):
        for record in self:
            record.approver_ids.validate_company(record.company_id)

    @api.constrains('state', 'approver_ids')
    def _check_approvers(self):
        for record in self:
            if record.state == 'inprogress' and not record.approver_ids:
                raise ValidationError(_('Please add at least one approver!'))

    @api.constrains('state', 'document_ids')
    def _check_documents(self):
        for record in self:
            if record.state == 'inprogress' and not record.document_ids:
                raise ValidationError(_('Please add at least one document!'))

    # Helpers
    def set_state(self, state, vals=None):
        if vals is None:
            vals = {}
        vals.update({'state': state})
        return self.write(vals)

    def get_next_approvers(self):
        self.ensure_one()
        next_approvers = self.approver_ids.filtered(lambda a: a.state == 'to approve').sorted('step')
        if not next_approvers:
            return next_approvers
        next_step = next_approvers[0].step
        return next_approvers.filtered(lambda a: a.step == next_step)

    def get_current_approvers(self):
        self.ensure_one()
        return self.approver_ids.filtered(lambda a: a.state == 'pending' and a.step == self.approval_step)

    def get_current_approver(self):
        self.ensure_one()
        current_approvers = self.get_current_approvers()
        if not current_approvers:
            raise UserError(_('There are not approvers for this document package!'))

        current_approver = current_approvers.filtered(lambda a: a.user_id == self.env.user)
        if not current_approver and self.env.user._is_admin():
            current_approver = current_approvers[0]
        if not current_approver:
            raise AccessError(_('You are not allowed to approve this document package!'))
        return current_approver

    def send_notification(self, view_ref, partner_ids):
        for record in self:
            record.message_post_with_view(
                view_ref,
                subject=_('Document Approval: %s') % record.name,
                composition_mode='mass_mail',
                partner_ids=[(6, 0, partner_ids)],
                auto_delete=False,
                auto_delete_message=False,
                parent_id=False,
                subtype_id=self.env.ref('mail.mt_note').id)

    # User actions

    def action_send_for_approval(self):
        for record in self:
            if record.state == 'draft' and record.approver_ids:
                # Subscribe approvers
                record.message_subscribe(partner_ids=record.approver_ids.mapped('user_id').mapped('partner_id').ids)
            if record.approval_state == 'pending':
                raise UserError(_('The document package have already been sent for approval!'))
            elif record.approval_state == 'approved':
                raise UserError(_('The document package have already been approved!'))
            elif record.approval_state == 'rejected':
                raise UserError(_('The document package was rejected! To send it for approval again, please update document(s) first.'))
            elif record.approval_state == 'to approve':
                next_approvers = record.get_next_approvers()
                print(f"mail next approvers {next_approvers}")
                if next_approvers:
                    if record.state == 'draft':
                        record.state = 'inprogress'
                    next_approvers.write({'state': 'pending'})
                    partner_ids = next_approvers.mapped('user_id').mapped('partner_id').ids
                    send_status = record.send_notification('xf_doc_approval.request_to_approve', partner_ids)
                    print(f"mail send status -> {send_status}")
                else:
                    raise UserError(_('There are not approvers for this document package!'))

    def action_approve_wizard(self):
        self.ensure_one()
        current_approver = self.get_current_approver()
        return current_approver.action_wizard('action_approve_wizard', _('Approve'))

    def action_reject_wizard(self):
        self.ensure_one()
        current_approver = self.get_current_approver()
        return current_approver.action_wizard('action_reject_wizard', _('Reject'))

    def action_draft(self):
        for record in self:
            record.approver_ids.write({'state': 'to approve', 'notes': None})
            record.write({'state': 'draft', 'reject_reason': None})
        return True

    def action_cancel(self):
        if not self.env.user._is_admin() and self.filtered(lambda record: record.state == 'approved'):
            raise UserError(_("Cannot cancel a document package that is approved."))
        return self.set_state('cancelled')

    def action_finish_approval(self):
        for record in self:
            if record.approval_state == 'approved':
                record.state = 'approved'
            else:
                raise UserError(_('Document Package must be fully approved!'))

    # Built-in methods

    # def unlink(self):
    #     if any(self.filtered(lambda record: record.state not in ('draft', 'rejected'))):
    #         raise UserError(_('You cannot delete a record which is not draft or rejected!'))
    #     return super(DocApprovalDocumentPackage, self).unlink()

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'inprogress':
            return self.env.ref('xf_doc_approval.mt_document_package_approval')
        elif 'state' in init_values and self.state == 'approved':
            return self.env.ref('xf_doc_approval.mt_document_package_approved')
        elif 'state' in init_values and self.state == 'cancelled':
            return self.env.ref('xf_doc_approval.mt_document_package_cancelled')
        elif 'state' in init_values and self.state == 'rejected':
            return self.env.ref('xf_doc_approval.mt_document_package_rejected')

        return super(DocApprovalDocumentPackage, self)._track_subtype(init_values)


class DocApprovalDocument(models.Model):
    _name = 'xf.doc.approval.document'
    _description = 'Document'

    document_package_id = fields.Many2one(
        string='Document Package',
        comodel_name='xf.doc.approval.document.package',
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
    )
    file = fields.Binary(
        string='File',
        required=True,
        attachment=True,
    )
    file_name = fields.Char(
        string='File Name'
    )

    @api.onchange('file_name')
    def _onchange_file_name(self):
        if self.file_name and not self.name:
            self.name = self.file_name


# class CopyFormWizard(models.TransientModel):
#     _name = 'copy.form.wizard'
#     _description = 'Copy Document Package Wizard'
#
#     original_id = fields.Many2one(
#         'xf.doc.approval.document.package',
#         string='Select Project to Copy From',
#         required=True
#     )
#     new_name = fields.Char(string="New Project Name", required=True)
#
#     def copy_record(self):
#         self.ensure_one()
#
#         if not self.original_id:
#             raise UserError(_("Please select a project to copy."))
#
#         # 1. Copy the main project
#         copy_vals = self.original_id.copy_data()[0]
#         copy_vals['name'] = self.new_name
#
#         # Remove one2many fields to handle separately
#         copy_vals.pop('document_ids', None)
#         copy_vals.pop('document_approval_ids', None)
#         copy_vals.pop('approver_ids', None)
#
#         # Reset states
#         copy_vals['state'] = 'draft'
#         copy_vals['approval_state'] = 'Draft'
#
#         # Create new project
#         new_project = self.env['xf.doc.approval.document.package'].create(copy_vals)
#
#         # 2. Copy document attachments
#         for document in self.original_id.document_ids:
#             document_vals = document.copy_data()[0]
#             document_vals.update({
#                 'document_package_id': new_project.id,
#             })
#             self.env['xf.doc.approval.document'].create(document_vals)
#
#         # 3. Copy approvers
#         for approver in self.original_id.approver_ids:
#             approver_vals = approver.copy_data()[0]
#             approver_vals.update({
#                 'document_package_id': new_project.id,
#                 'state': 'to approve',
#                 'notes': False,
#             })
#             self.env['xf.doc.approval.document.approver'].create(approver_vals)
#
#         # 4. Copy document approvals + formats
#         for approval in self.original_id.document_approval_ids:
#             approval_vals = approval.copy_data()[0]
#             approval_vals.update({
#                 'document_package_id': new_project.id,
#                 'status': 'draft',
#                 'formate_id': False,
#             })
#             new_approval = self.env['document.approval'].create(approval_vals)
#
#             if approval.formate_id:
#                 try:
#                     format_model = self.env[approval.formate.table]
#                     old_format_record = format_model.browse(int(approval.formate_id))
#
#                     if old_format_record.exists():
#                         # Step 1: Copy the parent format (without children)
#                         format_vals = old_format_record.copy_data()[0]
#                         format_vals.update({'project_id': new_project.id})
#
#                         # Remove possible one2many fields to prevent error
#                         child_fields = []
#                         for field in format_model._fields:
#                             if format_model._fields[field].type == 'one2many':
#                                 child_fields.append(field)
#
#                         for field in child_fields:
#                             format_vals.pop(field, None)
#
#                         new_format_record = format_model.create(format_vals)
#
#                         # Step 2: Now manually copy all one2many child lines
#                         for field in child_fields:
#                             child_records = old_format_record[field]
#                             if child_records:
#                                 for child in child_records:
#                                     child_vals = child.copy_data()[0]
#                                     # Update parent field
#                                     parent_field = format_model._fields[field].inverse_name
#                                     child_vals.update({parent_field: new_format_record.id})
#                                     self.env[child._name].create(child_vals)
#                                     print("test triggered")
#
#                         # Step 3: Finally link new formate to approval
#                         new_approval.write({'formate_id': str(new_format_record.id)})
#
#                 except Exception as e:
#                     _logger.error(f"Error copying formate_id and children for approval {approval.id}: {str(e)}")
#
#         # 5. Return action to open the new project
#         return {
#             'type': 'ir.actions.act_window',
#             'res_model': 'xf.doc.approval.document.package',
#             'res_id': new_project.id,
#             'view_mode': 'form',
#             'target': 'current',
#         }


# class CopyFormWizard(models.TransientModel):
#     _name = 'copy.form.wizard'
#     _description = 'Wizard to Copy Form'
#
#     original_id = fields.Many2one(
#         'xf.doc.approval.document.package',
#         string='Select Project to Copy From',
#         required=True
#     )
#     new_name = fields.Char(string="New Project Name", required=True)
#
#     def copy_record(self):
#         if not self.original_id:
#             raise UserError("Please select a project to copy.")
#
#         # 1. Copy the main project
#         copy_vals = self.original_id.copy_data()[0]
#         copy_vals['name'] = self.new_name
#
#         # Important: remove one2many fields
#         copy_vals.pop('document_ids', None)
#         copy_vals.pop('document_approval_ids', None)
#
#         new_project = self.env['xf.doc.approval.document.package'].create(copy_vals)
#
#         # 2. Copy document_ids (Files)
#         for document in self.original_id.document_ids:
#             new_document_vals = document.copy_data()[0]
#             new_document_vals.update({
#                 'document_package_id': new_project.id,
#             })
#             self.env['xf.doc.approval.document'].create(new_document_vals)
#
#         # 3. Copy document_approval_ids (Approval Lines)
#         for approval in self.original_id.document_approval_ids:
#             new_approval_vals = approval.copy_data()[0]
#
#             # --- COPY FORMATE_ID Record ---
#             new_formate_id = False
#             if approval.formate and approval.formate.table and approval.formate_id:
#                 formate_model = self.env[approval.formate.table]
#                 old_formate_record = formate_model.browse(int(approval.formate_id))
#                 if old_formate_record.exists():
#                     new_formate_vals = old_formate_record.copy_data()[0]
#
#                     # Remove child one2many fields from main copy (temporary)
#                     if 'operation_ids' in new_formate_vals:
#                         new_formate_vals.pop('operation_ids')
#
#                     new_formate_record = formate_model.create(new_formate_vals)
#
#                     # Now manually copy child lines
#                     for operation in old_formate_record.operation_ids:
#                         new_operation_vals = operation.copy_data()[0]
#                         new_operation_vals.update({
#                             'parent_id': new_formate_record.id,  # Link to new formate
#                         })
#                         self.env[operation._name].create(new_operation_vals)
#
#                     new_formate_id = str(new_formate_record.id)
#
#             # --- Now update approval line values ---
#             new_approval_vals.update({
#                 'document_package_id': new_project.id,
#                 'status': 'draft',
#                 'formate_id': new_formate_id,  # Set new copied formate_id
#             })
#
#             self.env['document.approval'].create(new_approval_vals)
#
#         return {
#             'type': 'ir.actions.act_window',
#             'res_model': 'xf.doc.approval.document.package',
#             'res_id': new_project.id,
#             'view_mode': 'form',
#             'target': 'current',
#         }

#
# class CopyFormWizard(models.TransientModel):
#     _name = 'copy.form.wizard'
#     _description = 'Wizard to Copy Form'
#
#     original_id = fields.Many2one(
#         'xf.doc.approval.document.package',
#         string='Select Project to Copy From',
#         required=True
#     )
#     new_name = fields.Char(string="New Project Name", required=True)
#
#     def copy_record(self):
#         if not self.original_id:
#             raise UserError("Please select a project to copy.")
#
#         # 1. Copy the main project
#         copy_vals = self.original_id.copy_data()[0]
#         copy_vals['name'] = self.new_name
#
#         # Important: remove one2many fields from main project
#         copy_vals.pop('document_ids', None)
#         copy_vals.pop('document_approval_ids', None)
#
#         new_project = self.env['xf.doc.approval.document.package'].create(copy_vals)
#
#         # 2. Copy document_ids (Files)
#         for document in self.original_id.document_ids:
#             new_document_vals = document.copy_data()[0]
#             new_document_vals.update({
#                 'document_package_id': new_project.id,
#
#             })
#             self.env['xf.doc.approval.document'].create(new_document_vals)
#
#         # 3. Copy document_approval_ids (Approvals)
#         for approval in self.original_id.document_approval_ids:
#             new_approval_vals = approval.copy_data()[0]
#
#             # Reset important fields
#             new_approval_vals.update({
#                 'document_package_id': new_project.id,
#                 'status': 'draft',  # force status reset
#                 'formate_id': False,  # clear old formate_id
#             })
#
#             new_approval = self.env['document.approval'].create(new_approval_vals)
#
#             # very important: call create_formate manually if needed
#             # new_approval.create_formate()
#
#         return {
#             'type': 'ir.actions.act_window',
#             'res_model': 'xf.doc.approval.document.package',
#             'res_id': new_project.id,
#             'view_mode': 'form',
#             'target': 'current',
#         }
#

# class CopyFormWizard(models.TransientModel):
#     _name = 'copy.form.wizard'
#     _description = 'Wizard to Copy Form'
#
#     original_id = fields.Many2one(
#         'xf.doc.approval.document.package',
#         string='Select Project to Copy From',
#         required=True
#     )
#     new_name = fields.Char(string="New Project Name", required=True)
#
#     def copy_record(self):
#         if not self.original_id:
#             raise UserError("Please select a project to copy.")
#
#         # 1. Copy the main project
#         copy_vals = self.original_id.copy_data()[0]
#         copy_vals['name'] = self.new_name
#
#         # remove One2many fields
#         copy_vals.pop('document_ids', None)
#         copy_vals.pop('document_approval_ids', None)
#
#         new_project = self.env['xf.doc.approval.document.package'].create(copy_vals)
#
#         # 2. Copy all Documents (attached files)
#         for document in self.original_id.document_ids:
#             new_document_vals = document.copy_data()[0]
#             new_document_vals.update({
#                 'document_package_id': new_project.id,
#             })
#             self.env['xf.doc.approval.document'].create(new_document_vals)
#
#         # 3. Copy all Document Approval Lines
#         for approval in self.original_id.document_approval_ids:
#             new_approval_vals = approval.copy_data()[0]
#             new_approval_vals.update({
#                 'document_package_id': new_project.id,
#             })
#             self.env['document.approval'].create(new_approval_vals)
#
#         return {
#             'type': 'ir.actions.act_window',
#             'res_model': 'xf.doc.approval.document.package',
#             'res_id': new_project.id,
#             'view_mode': 'form',
#             'target': 'current',
#         }


class DocumentApproval(models.Model):
    _name = 'document.approval'
    _description = 'Document'
    _order = 'sr_no asc'

    document_package_id = fields.Many2one(
        string='Document Package',
        comodel_name='xf.doc.approval.document.package',
        ondelete='cascade',
    )
    serial_no = fields.Integer(string='Serial No.')
    sr_no = fields.Integer(string='Sequence No.')
    plan_start_date = fields.Date("Plan Start Date")
    plan_end_date = fields.Date("Plan End Date")
    actual_start_date = fields.Date("Actual Start Date")
    actual_end_date = fields.Date("Actual End Date")
    name = fields.Char(string='Package Name')
    formate = fields.Many2one('document.formate', string='Format')
    control_emp_ids = fields.Many2many('hr.employee', 'emp_idxx', string='Control Employee')
    control_department_ids = fields.Many2many('hr.department', 'dep_idsxx', string='Control Departments', compute='_compute_approval_departments')

    department_ids = fields.Many2many('hr.department', string='Departments', compute='_compute_approval_departments')
    manager_ids = fields.Many2many('hr.employee', string='Approved By')
    formate_id = fields.Char('Format Id')
    # status = fields.Char('Status', compute='_compute_approval_status')
    status = fields.Selection([('draft', 'Draft'), ('pending', 'Pending'),
                                     ('approved', 'Approved'),
                                     ('revision', 'Revision Required'),
                                     ('rejected', 'Rejected')],
                                    string='Status', compute='_compute_approval_status')
    used_in_project_type_ids = fields.Many2many(string='Used in Project type', comodel_name='doc.project.type')
    check_create_emp = fields.Boolean(compute='_check_create_employee')
    check_sequence = fields.Boolean('Check Sequence')
    include_vals = fields.Boolean(string="Include Values", default=True)

    # def _compute_approval_status(self):
    #     for rec in self:
    #         if rec.formate_id:
    #             formate_id = self.env[rec.formate.table].sudo().search([('id', '=', rec.formate_id)])
    #             if formate_id and formate_id.approve_department_ids.ids == formate_id.approve_by_department_ids.ids:
    #                 rec.status = 'Approved'
    #             else:
    #                 rec.status = 'Approval Inprogress'
    #         else:
    #             rec.status = 'Draft'

    def _compute_approval_status(self):
        for rec in self:
            rec.status = 'pending'
            # rec.actual_start_date = False
            # rec.actual_end_date = False

            # Skip if it's an independent document
            if not rec.include_vals or not rec.formate_id or not rec.formate or not rec.formate.table:
                continue

            model = self.env[rec.formate.table]

            try:
                formate_id_int = int(rec.formate_id)
            except (ValueError, TypeError):
                continue

            current_record = model.browse(formate_id_int)
            if not current_record.exists():
                continue

            if 'final_status' in current_record._fields:
                rec.status = current_record.final_status or 'pending'
            if 'actual_start_date' in current_record._fields:
                rec.actual_start_date = current_record.actual_start_date
            if 'actual_end_date' in current_record._fields:
                rec.actual_end_date = current_record.actual_end_date


    @api.depends('control_emp_ids', 'manager_ids')
    def _compute_approval_departments(self):
        for rec in self:
            department_ids = rec.control_emp_ids.mapped('department_id')
            rec.control_department_ids = [(6, 0, department_ids.ids)]
            department_ids = self.env['hr.department'].search([]).filtered(lambda l:l.manager_id.id in rec.manager_ids.ids)
            rec.department_ids = [(6, 0, department_ids.ids)]


    # def create_formate(self):
    #     vals = {
    #     'document_name' : self.document_package_id.name,
    #     'approve_department_ids' : [(6, 0, self.department_ids.ids)],
    #     'manager_ids' : [(6, 0, self.manager_ids.ids)],
    #     }
    #     formate_id = self.env[self.formate.table].sudo().create(vals)
    #     self.formate_id = formate_id.id

    def create_formate(self):
        if not self.formate or not self.formate.table:
            raise ValidationError("Format or format table is not set.")

        if self.include_vals:
            if not self.document_package_id:
                raise ValidationError("Document Package must be set.")
            if not self.manager_ids:
                raise ValidationError("Please configure Approvers for the Document")
            if not self.plan_start_date or not self.plan_end_date:
                raise ValidationError("Please configure both Plan Start Date and Plan End Date")
            if self.plan_start_date > self.plan_end_date:
                raise ValidationError("Start date cannot be after end date.")

            iatf_member_data_ids = []
            for manager in self.manager_ids:
                iatf_member_data = self.env['iatf.members.data'].create({
                    'approver_id': manager.id,
                    'approval_status': 'pending',
                })
                iatf_member_data_ids.append(iatf_member_data.id)

            vals = {
                'project_id': self.document_package_id.id,
                'doc_type': self.document_package_id.doc_type,
                'part_id': self.document_package_id.part_id.id,
                'partner_id': self.document_package_id.partner_id.id,
                'plan_start_date': self.plan_start_date,
                'plan_end_date': self.plan_end_date,
                'iatf_members_ids': [(6, 0, iatf_member_data_ids)],
                'actual_start_date': fields.Date.context_today(self),
            }

            # Create format record for non-independent documents
            formate_id = self.env[self.formate.table].sudo().create(vals)
            self.formate_id = str(formate_id.id)  # Ensure string type for Char field

            return {
                'type': 'ir.actions.act_window',
                'name': self.formate.name,
                'view_mode': 'form',
                'res_model': self.formate.table,
                'res_id': formate_id.id,
                'target': 'current',
                'context': {'create': False, 'default_formate_id': self.id}
            }
        else:
            # For independent documents, create a minimal record just to establish the link
            formate_id = self.env[self.formate.table].sudo().create({})
            self.formate_id = str(formate_id.id)

            return {
                'type': 'ir.actions.act_window',
                'name': self.formate.name,
                'view_mode': 'form',
                'res_model': self.formate.table,
                'res_id': formate_id.id,
                'target': 'new',
                'context': {'default_formate_id': self.id}
            }

    @api.onchange('formate')
    def _onchage_department_id(self):
        for department in self.formate.department_ids:
            self.department_ids = [(4, department.id)]
        # self.control_department_ids = [(6, 0, self.control_emp_ids.mapped('department_id').ids)]

    def open_formate(self):
        formate_id = self.env[self.formate.table].sudo().search([('id', '=', self.formate_id)])
        return {
                'type': 'ir.actions.act_window',
                'name': self.formate.name,
                'view_mode': 'form',
                # 'target': 'new',
                'res_model': self.formate.table,
                'res_id': formate_id.id,
                'context': {'create': False}
            }

    def _check_create_employee(self):
        for rec in self:
            # if self.env.user.employee_id.department_id.id in rec.control_emp_ids.ids and self.env.user.employee_id.department_id.department_type == 'hr':
            is_admin = self.env.user.id == 1 or self.env.user.has_group('base.group_system')

            if is_admin or self.env.user.employee_id.id in rec.control_emp_ids.ids:
                rec.check_create_emp = True
            else:
                rec.check_create_emp = False

    def write(self, vals):
        res = super().write(vals)
        if 'manager_ids' in vals and self.include_vals:
            if self.status == "approved":
                raise ValidationError(_("Cannot Change Approver of approved document"))
            else:
                iatf_member_data_ids = []
                for manager in self.manager_ids:
                    iatf_member_data = self.env['iatf.members.data'].create({
                        'approver_id': manager.id,
                        'approval_status': 'pending',
                    })
                    iatf_member_data_ids.append(iatf_member_data.id)
                formate_id = self.env[self.formate.table].sudo().search([('id', '=', self.formate_id)])
                if formate_id and 'iatf_members_ids' in formate_id._fields:
                    formate_id.iatf_members_ids = [(6, 0, iatf_member_data_ids)]

        return res

