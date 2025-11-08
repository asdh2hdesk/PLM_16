from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from logging import getLogger
import datetime

_logger = getLogger(__name__)

class ProductTemplateInherited(models.Model):
    _inherit = "product.template"

    customer_part_creation_id = fields.Many2one('customer.part.creation', 'Customer part id')
    drg_no = fields.Char("Drawing Nooo.")
    drg_revision_no = fields.Char("Drawing Revision No.")
    drg_revision_date = fields.Date("Drawing Revision Date")

    customer_id = fields.Many2one('res.partner','Customer Name')
    customer_part_name = fields.Char('Customer Part Name')
    customer_part_no = fields.Char('Customer Part No.')


class MembersData(models.Model):
    _name = 'iatf.members.data'
    # _inherit = "translation.mixin"

    approval_status = fields.Selection([('draft', 'Draft'), ('pending', 'Pending'),
                                        ('approved', 'Approved'),
                                        ('revision', 'Revision Required'),
                                        ('rejected', 'Rejected')],
                                       string='Status', default='pending')
    approver_id = fields.Many2one('hr.employee', 'Approver')
    date_approved_rejected = fields.Date('Approved/Rejected Date')
    department_id = fields.Many2one('hr.department', 'Department', related='approver_id.department_id', store=True, readonly=True)
    comment = fields.Char('Comment')


class IATFSignOffMembers(models.AbstractModel):
    _name = 'iatf.sign.off.members'
    _inherit = "translation.mixin"

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('hold', 'Hold'),
        ('confirm', 'Confirm'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)
    project_id = fields.Many2one('xf.doc.approval.document.package', string='Project Name', readonly=True)
    iatf_members_ids = fields.Many2many('iatf.members.data', string='Approvers')
    final_status = fields.Selection([('draft', 'Draft'), ('pending', 'Pending'),
                                     ('approved', 'Approved'),
                                     ('revision', 'Revision Required'),
                                     ('rejected', 'Rejected')],
                                    string='Status',compute='_compute_final_status')
    show_buttons = fields.Boolean(default=False)
    link = fields.Char()
    user_has_access_to_approve = fields.Boolean(string='User Has Access', compute='_compute_user_has_access')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )
    doc_type = fields.Selection([('safelaunch', 'Safe Launch'), ('prototype', 'Prototype'), ('prelaunch', 'PreLaunch'),
                             ('production', 'Production')])
    part_id = fields.Many2one("product.template", string="Product")
    part_name = fields.Char("Product Name", related="part_id.name")
    part_number = fields.Char("Product Number", related="part_id.default_code")
    drawing_no = fields.Char("Drawing No.", related="part_id.drg_no")
    drawing_rev_no = fields.Char("Drawing. Rev. No.", related="part_id.drg_revision_no")
    drawing_rev_date = fields.Date("Drawing Rev. Date", related="part_id.drg_revision_date")
    part_description = fields.Text("Part Description")
    partner_id = fields.Many2one('res.partner', string='Customer Name')
    cft_team = fields.Many2many('res.users', string='CFT Team')
    customer_part_name = fields.Char("Customer Part name",translate=True)
    cus_id = fields.Many2one('product.template',"Customer name")
    cus_part_name = fields.Char("Customer Part name", related='cus_id.customer_part_name')
    cus_part_no = fields.Char("Customer Part num", related='cus_id.customer_part_no')

    member_name = fields.Char("Member Name")

    @api.depends('iatf_members_ids')
    def _compute_user_has_access(self):
        for record in self:
            employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
            approver_id_list = record.iatf_members_ids.mapped(lambda x: x.approver_id.id)
            if employee.id in approver_id_list:
                record.user_has_access_to_approve = True
            else:
                record.user_has_access_to_approve = False

    @api.depends('iatf_members_ids')
    def _compute_final_status(self):
        for record in self:
            statuses = record.iatf_members_ids.mapped('approval_status')
            total_records = len(statuses)

            if record.state != 'draft':
                if total_records == statuses.count('approved'):
                    record.final_status = 'approved'
                elif 'rejected' in statuses:
                    record.final_status = 'rejected'
                elif 'revision' in statuses:
                    record.final_status = 'revision'
                else:
                    record.final_status = 'pending'
            else:
                record.final_status = 'draft'

    def _open_action_wizard(self, action):
        current_user = self.env.user
        employee = self.env['hr.employee'].search([('user_id', '=', current_user.id)], limit=1)
        if not employee:
            raise ValidationError(_('You are not linked to any employee record.'))
        for rec in self:
            user_member_records = rec.iatf_members_ids.filtered(lambda m: m.approver_id.id == employee.id)
            if user_member_records:
                message = {
                    'approve': _('Do you want to approve the document?'),
                    'reject': _('Do you want to reject the document?'),
                    'revise': _('Do you want to revise the document?')
                }.get(action, '')
                return {
                    'name': _('Document Action'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'approve.document.wizard',
                    'view_mode': 'form',
                    'view_id': self.env.ref('iatf.view_approve_document_wizard').id,
                    'target': 'new',
                    'context': {
                        'default_action': action,
                        'default_message': message,
                        'active_id': rec.id,
                        'active_model': self._name
                    }
                }
            else:
                raise ValidationError(_('You are not an Approver for the current Document.'))

    def action_confirm(self):
        for rec in self:
            rec.state = 'confirm'
        # After confirm, show Approve, Revise, Reject buttons (handled in view)

    def approve_document(self):
        for rec in self:
            rec.state = 'approved'
        return self._open_action_wizard('approve')

    def reject_document(self):
        for rec in self:
            rec.state = 'rejected'
        return self._open_action_wizard('reject')

    def revise_document(self):
        # Start advanced revision process
        for rec in self:
            # Open the advanced revision wizard
            return {
                'name': _('Start Document Revision'),
                'type': 'ir.actions.act_window',
                'res_model': 'advanced.revision.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_res_model': rec._name,
                    'default_res_id': rec.id,
                    'default_current_revision': getattr(rec, 'current_revision_number', '0'),
                    'default_document_name': rec.display_name,
                }
            }

    def get_form_view_action_external_ids(self):
        # Get the environment
        env = self.env  # if used in a controller, or self.env in a model method

        # Search for window actions associated with the given model
        window_actions = env['ir.actions.act_window'].search(
            [('res_model', '=', self._name), ('view_mode', 'like', 'form')])

        # Initialize a list to store the details of the form view window actions
        form_view_action_details = []

        for action in window_actions:
            # Search for the external ID in ir.model.data
            external_id = env['ir.model.data'].search([
                ('model', '=', 'ir.actions.act_window'),
                ('res_id', '=', action.id)
            ], limit=1).complete_name

            # Store the form view action details in the list
            form_view_action_details.append({
                'name': action.name,
                'external_id': external_id,
                'view_mode': action.view_mode,
            })
        return form_view_action_details

    def send_mail(self, mail_template_xml, email_list):
        _logger.info("Starting send_mail with template: %s", mail_template_xml)

        mail_template = self.env.ref(mail_template_xml, raise_if_not_found=False)
        if not mail_template:
            raise ValidationError(_("Mail template not found: %s") % mail_template_xml)

        model_id = self.env['ir.model'].sudo().search([('model', '=', self._name)])
        mail_template.write({'model_id': model_id.id})

        web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        external_id_data_of_act_window = self.get_form_view_action_external_ids()

        # Use the first external_id found
        action_id = self.env.ref(external_id_data_of_act_window[0]['external_id'], raise_if_not_found=False)

        link = "{}/web#id={}&view_type=form&model={}&action={}".format(
            web_base_url, self.id, self._name, action_id.id if action_id else '')
        self.link = link

        # Clean the email list: remove None / False / empty strings
        clean_emails = list(filter(None, email_list))

        if not clean_emails:
            raise ValidationError(_("No valid email addresses found to send mail."))

        email_ids = ','.join(clean_emails)

        _logger.info("Sending mail to emails: %s", email_ids)

        mail_template.write({
            'email_to': email_ids,
        })
        mail_template.send_mail(self.id, force_send=True)

        _logger.info("Mail sent successfully to: %s", email_ids)

    def get_email_list(self):
        email_list = set()
        for rec in self:
            for member in rec.iatf_members_ids:
                email = member.approver_id.user_id.login
                if not email:
                    raise ValidationError(
                        _(f"Please configure Login email for {member.approver_id.name} from {member.department_id.name}"))
                else:
                    email_list.add(email)
            project_initiator_mail_id = rec.project_id.create_uid.login
            _logger.info(f"Project initiator mail [{project_initiator_mail_id}]")
            if project_initiator_mail_id:
                email_list.add(project_initiator_mail_id)

            document_creator_mail = rec.create_uid.login
            _logger.info(f"Document creator mail [{document_creator_mail}]")
            if document_creator_mail:
                email_list.add(document_creator_mail)

            control_employee_mail = rec.project_id.document_approval_ids.filtered(lambda x: x.formate_id == str(rec.id))

            if control_employee_mail:
                _logger.info(f"Control employees {control_employee_mail.control_emp_ids}")
                for employee in control_employee_mail.control_emp_ids:
                    if employee.user_id.login:
                        email_list.add(employee.user_id.login)
                    else:
                        raise ValidationError(
                            _(f"Please configure Login email for {employee.user_id} from {employee.department_id.name}"))
        return email_list


    def send_for_approval(self):
        # Determine the appropriate mail template based on the model
        if self._name == 'control.plan':
            mail_template = 'iatf.iatf_control_plan_approval_mail_template'
        elif self._name == 'process.flow':
            mail_template = 'iatf.iatf_process_flow_approval_mail_template'
        elif self._name == 'asd.pfmea':
            mail_template = 'iatf.iatf_pfmea_approval_mail_template'
        else:
            # Fallback to generic template
            mail_template = 'iatf.mom_document_approval_mail_template'
            
        email_list = self.get_email_list()
        employee = self.env['hr.employee'].search([('user_id', '=', self.create_uid.id)], limit=1)
        if employee:
            email_list.add(employee.work_email)
        self.send_mail(mail_template, email_list)

        self.state = 'confirm'

    def send_document_fully_approved_mail(self):
        # Determine the appropriate mail template based on the model
        if self._name == 'control.plan':
            mail_template = 'iatf.iatf_control_plan_fully_approved_mail_template'
        elif self._name == 'process.flow':
            mail_template = 'iatf.iatf_process_flow_fully_approved_mail_template'
        elif self._name == 'asd.pfmea':
            mail_template = 'iatf.iatf_pfmea_fully_approved_mail_template'
        else:
            # Fallback to generic template
            mail_template = 'iatf.mom_document_fully_approved_mail_template'
            
        email_list = self.get_email_list()
        self.send_mail(mail_template, email_list)

    def send_document_approved_by_user_mail(self, user):
        # Determine the appropriate mail template based on the model
        if self._name == 'control.plan':
            mail_template = 'iatf.iatf_control_plan_approved_by_user_mail_template'
        elif self._name == 'process.flow':
            mail_template = 'iatf.iatf_process_flow_approved_by_user_mail_template'
        elif self._name == 'asd.pfmea':
            mail_template = 'iatf.iatf_pfmea_approved_by_user_mail_template'
        else:
            # Fallback to generic template
            mail_template = 'iatf.approved_mail_template'
            
        email_list = self.get_email_list()

        # do not send the document approved by mail to the user if he approved and document is still in pending stage
        if user.login in email_list:
            email_list.remove(user.login)
        self.send_mail(mail_template, email_list)


    def send_revision_required_mail_by_user(self, user):
        # Determine the appropriate mail template based on the model
        if self._name == 'control.plan':
            mail_template = 'iatf.iatf_control_plan_revision_required_mail_template'
        elif self._name == 'process.flow':
            mail_template = 'iatf.iatf_process_flow_revision_required_mail_template'
        elif self._name == 'asd.pfmea':
            mail_template = 'iatf.iatf_pfmea_revision_required_mail_template'
        else:
            # Fallback to generic template
            mail_template = 'iatf.mom_document_revision_requested_mail_template'
            
        email_list = self.get_email_list()
        self.send_mail(mail_template, email_list)

    def send_approved_mail(self):
        mail_template = self.env.ref('iatf.mom_document_approved_mail_template')
        model_id = self.env['ir.model'].sudo().search([('model', '=', self._name)])
        mail_template.write({'model_id': model_id.id})

        web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        external_id_data_of_act_window = self.get_form_view_action_external_ids()

        action_id = self.env.ref(external_id_data_of_act_window[0]['external_id'], raise_if_not_found=False)

        link = """{}/web#id={}&view_type=form&model=self._name&action={}""".format(web_base_url, self.id, action_id.id)
        self.link = link

        email_list = []
        for rec in self:
            for member in rec.iatf_members_ids:
                email = member.approver_id.user_id.login
                if not email:
                    raise ValidationError(_(f"Please configure Login email for {member.name} from {member.department_id.name}"))
                else:
                    email_list.append(email)

        # Filter out None / False values safely
        email_ids = ','.join(filter(None, email_list))

        mail_template.write({
            'email_to': email_ids,
        })
        mail_template.send_mail(self.id, force_send=True)


    # Remove legacy revision logic
    # def set_to_draft(self): ...
    # def create_copy_add_for_revision(self): ...
    # def create_deep_copy(self): ...


class ApproveDcoumentWizard(models.TransientModel):
    _name = 'approve.document.wizard'
    _description = 'Approve Document Wizard'
    # _inherit = "translation.mixin"

    comment = fields.Char('Comment')
    action = fields.Selection([('approve', 'Approve'), ('reject', 'Reject'), ('revise', 'Revise')])

    def confirm_action(self):
        context = dict(self._context or {})
        active_id = context.get('active_id')
        active_model = context.get('active_model')

        if active_id and active_model:
            document = self.env[active_model].browse(active_id)
            current_user = self.env.user
            employee = self.env['hr.employee'].search([('user_id', '=', current_user.id)], limit=1)

            if not employee:
                raise ValidationError(_('You are not linked to any employee record.'))

            user_member_records = document.iatf_members_ids.filtered(lambda m: m.approver_id.id == employee.id)

            if user_member_records:
                if self.action == 'approve':
                    user_member_records.write({
                        'approval_status': 'approved',
                        'comment': self.comment,
                        'date_approved_rejected': fields.Date.today()
                    })

                    document._compute_final_status()
                    if document.final_status == 'approved':
                        document.send_document_fully_approved_mail()
                    elif document.final_status == 'pending':
                        document.send_document_approved_by_user_mail(current_user)

                elif self.action == 'reject':
                    user_member_records.write({
                        'approval_status': 'rejected',
                        'comment': self.comment,
                        'date_approved_rejected': fields.Date.today()
                    })
                elif self.action == 'revise':
                    user_member_records.write({
                        'approval_status': 'revision',
                        'comment': self.comment,
                        'date_approved_rejected': fields.Date.today()
                    })
                    document._compute_final_status()
                    if document.final_status == 'revision':
                        document.create_copy_add_for_revision()
                        document.send_revision_required_mail_by_user(current_user)
            else:
                raise ValidationError(_('You are not an Approver for the current document.'))


class RevisionHistory(models.Model):
    _name = 'document.revision.history'
    _description = 'Document Revision History'
    _order = 'rev_date desc, rev_no desc'
    _inherit = "translation.mixin"

    serial_no = fields.Char('Serial No.')
    rev_no = fields.Char('Revision No.')
    rev_date = fields.Date('Revision Date', default=fields.Date.today)
    revision_details = fields.Text('Revision Details',translate=True)
    revised_by = fields.Many2one('res.users', string='Revised By', default=lambda self: self.env.user)

    # Generic reference fields to connect to any model
    res_model = fields.Char('Resource Model')
    res_id = fields.Integer('Resource ID')


class RevisionHistoryMixin(models.AbstractModel):
    _name = 'revision.history.mixin'
    _description = 'Revision History Mixin'
    # _inherit = "translation.mixin"

    revision_history_ids = fields.One2many(
        'document.revision.history',
        compute='_compute_revision_history_ids',
        string='Revision History'
    )

    rev_no = fields.Char('Revision No.', default='0', tracking=True)
    rev_date = fields.Date('Revision Date', default=fields.Date.today)

    def _compute_revision_history_ids(self):
        for record in self:
            record.revision_history_ids = self.env['document.revision.history'].search([
                ('res_model', '=', self._name),
                ('res_id', '=', record.id)
            ], order='rev_date desc, id desc')

    @api.model
    def create(self, vals):
        # Set initial revision when creating a new record
        if 'rev_no' not in vals:
            vals['rev_no'] = '0'
        if 'rev_date' not in vals:
            vals['rev_date'] = fields.Date.today()

        record = super(RevisionHistoryMixin, self).create(vals)

        # Create initial revision history entry
        self.env['document.revision.history'].create({
            'serial_no': f"{record._name}-{record.id}-0",
            'rev_no': record.rev_no,
            'rev_date': record.rev_date,
            'revision_details': 'Initial Revision',
            'revised_by': self.env.user.id,
            'res_model': record._name,
            'res_id': record.id,
        })

        return record

    def write(self, vals):
        # Check if rev_no is being updated
        if 'rev_no' in vals or 'rev_date' in vals:
            for record in self:
                # Prepare revision details
                details = "Document updated"
                if vals.get('rev_no'):
                    details = f"Revision updated to {vals['rev_no']}"

                # Create revision history entry
                self.env['document.revision.history'].create({
                    'serial_no': f"{record._name}-{record.id}-{vals.get('rev_no', record.rev_no)}",
                    'rev_no': vals.get('rev_no', record.rev_no),
                    'rev_date': vals.get('rev_date', fields.Date.today()),
                    'revision_details': details,
                    'revised_by': self.env.user.id,
                    'res_model': record._name,
                    'res_id': record.id,
                })

        return super(RevisionHistoryMixin, self).write(vals)

    def add_revision(self, revision_details, rev_no=None, rev_date=None):
        """
        Add a new revision history entry and update document revision number
        :param revision_details: Description of changes made
        :param rev_no: Optional revision number (will auto-increment if not provided)
        :param rev_date: Optional revision date (will use today if not provided)
        """
        self.ensure_one()

        if not rev_no:
            # Auto-increment revision number
            try:
                rev_no = str(int(self.rev_no or '0') + 1)
            except ValueError:
                rev_no = '1'  # Start at 1 if previous revision isn't numeric

        if not rev_date:
            rev_date = fields.Date.today()

        # Update the document itself
        self.write({
            'rev_no': rev_no,
            'rev_date': rev_date
        })

        # History entry is created by the write method

        return True


class DocumentRevisionWizard(models.TransientModel):
    _name = 'document.revision.wizard'
    _description = 'Create Document Revision'
    # _inherit = "translation.mixin"

    res_model = fields.Char('Resource Model')
    res_id = fields.Integer('Resource ID')
    current_rev = fields.Char('Current Revision')
    new_rev = fields.Char('New Revision Number', required=True)
    rev_date = fields.Date('Revision Date', default=fields.Date.today)
    revision_details = fields.Text('Revision Details', required=True)

    def action_create_revision(self):
        record = self.env[self.res_model].browse(self.res_id)
        record.add_revision(
            revision_details=self.revision_details,
            rev_no=self.new_rev,
            rev_date=self.rev_date
        )
        return {'type': 'ir.actions.act_window_close'}