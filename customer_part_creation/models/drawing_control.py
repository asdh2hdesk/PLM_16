from sympy import false

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProductProduct(models.Model):
    _inherit = 'product.template'

    product_description = fields.Text(
        string='Product Description',
            help="Add full product description here"
        )

class DocumentCategory(models.Model):
    _name = 'document.category'
    _description = 'Document Category'
    _inherit = "translation.mixin"

    name = fields.Char(string='Category Name', required=True,translate=True)

# Main Document Control model
class DrawingDocument(models.Model):
    _name = 'document.control'
    _inherit = ['mail.thread', 'mail.activity.mixin', "translation.mixin"]
    _description = 'Drawing Control Document'
    _rec_name = 'sequence'

    sequence = fields.Char(string='Sr. No', readonly=True, default=lambda self: _('New'))
    name = fields.Char(string='Format Number', required=False, tracking=True,translate=True)
    part_number_id = fields.Many2one('product.product', string='Part Number', tracking=True)
    part_description = fields.Char(string='Part Description', related='part_number_id.name', readonly=True,translate=True)
    customer_name = fields.Many2one('res.partner', string='Customer Name', tracking=True)
    customer_part_number = fields.Char(string='Customer Part Number')
    customer_part_description = fields.Char(string='Customer Part Description',translate=True)
    customer_drawing = fields.Html(string='Customer Drawing')
    customer_drawing_attachment = fields.Binary(string='Customer Drawing Attachment', attachment=True)
    customer_drawing_filename = fields.Char(string='Customer Drawing Filename')
    current_drawing_revision = fields.Many2one(
        'document.revision', 
        string='Current Drawing Revision',
        compute='_compute_current_revision',
        store=True
    )
    
    current_drawing_revision_details = fields.Char(
        string='Current Drawing Revision Details',
        compute='_compute_current_revision',
        store=True,
        readonly=True
    )
    category_ids = fields.Many2many('document.category', string='Category')
    date_creation = fields.Date(string='Date of Creation', default=fields.Date.today, tracking=True)
    drawing_internal = fields.Html(string='Drawing Upload Internal')
    # drawing_internal_attachment = fields.Binary(string='Internal Drawing Attachment', attachment=True)
    drawing_internal_attachment_ids = fields.One2many(
        'ir.attachment',
        'res_id',
        domain=[('res_model', '=', 'document.control'), ('res_field', '=', 'drawing_internal_attachment_ids')],
        string='Attachments'
    )

    # Count field (optional, useful for displaying count)
    attachment_count = fields.Integer(
        string='Attachment Count',
        compute='_compute_attachment_count'
    )

    @api.depends('drawing_internal_attachment_ids')
    def _compute_attachment_count(self):
        for record in self:
            record.attachment_count = len(record.drawing_internal_attachment_ids)
    drawing_internal_filename = fields.Char(string='Internal Drawing Filename')
    release_to = fields.Many2many('res.users', string='Release To')
    current_revision_id = fields.Many2one('document.revision', string='Current Revision')
    revision_ids = fields.One2many('document.revision', 'document_id', string='Revisions')
    release_date = fields.Datetime(string='Release Date', readonly=True)
    released_by = fields.Many2one('res.users', string='Released By', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('released', 'Released'),
        ('cancled', 'Cancled'),
    ], string='Status', default='draft', tracking=True)
    approved_by = fields.Many2many(
        'res.users',
        relation='document_control_approved_by_rel',
        string='Approved By'
    )
    to_be_approved_by = fields.Many2many(
        'res.users',
        relation='document_control_to_be_approved_by_rel',
        string='To Be Approved By'
    )

    @api.model
    def create(self, vals):
        config = self.env['document.approval.config'].search([], limit=1)
        if config:
            vals['to_be_approved_by'] = [(6, 0, config.approver_ids.ids)]
        else:
            vals['to_be_approved_by'] = [(6, 0, [])]
        if vals.get('sequence', _('New')) == _('New'):
            vals['sequence'] = self.env['ir.sequence'].next_by_code('document.control') or _('New')
        return super(DrawingDocument, self).create(vals)

    @api.depends('revision_ids', 'revision_ids.revision_description')
    def _compute_current_revision(self):
        for record in self:
            if record.revision_ids:
                # Get the latest revision based on creation date/id
                latest_revision = record.revision_ids.sorted('id', reverse=True)[0]
                record.current_drawing_revision = latest_revision
                record.current_drawing_revision_details = latest_revision.revision_description or ''
            else:
                record.current_drawing_revision = False
                record.current_drawing_revision_details = ''
    
    
    def action_release_document(self):
        self.ensure_one()
        self.write({
            'state': 'released',
            'release_date': fields.Datetime.now(),
            'released_by': self.env.user.id
        })
        template = self.env.ref('customer_part_creation.email_template_document_released')
        for user in self.release_to:
            if user.email:
                email_values = {'email_to': user.email}
                context = {'recipient_user': user}
                template.with_context(**context).send_mail(self.id, force_send=True, email_values=email_values)

    def action_request_approval(self):
        self.ensure_one()
        self.write({
            'state': 'pending_approval',
            'approved_by': [(5, 0, 0)]
        })

    def action_approve(self):
        self.ensure_one()
        # Check if user has approver or manager rights
        if not (self.env.user.has_group('customer_part_creation.group_document_approver')):
            raise UserError("You don't have permission to approve documents.")
        if self.env.user not in self.to_be_approved_by:
            raise UserError("You are not authorized to approve this document.")
        if self.env.user in self.approved_by:
            raise UserError("You have already approved this document.")
        self.write({'approved_by': [(4, self.env.user.id)]})
        if all(approver in self.approved_by for approver in self.to_be_approved_by):
            self.write({'state': 'approved'})


    def action_new_revision(self):
        self.ensure_one()
        # Check if there is any existing revision not in 'released' state
        for revision in self.revision_ids:
            if revision.state != 'released':
                raise UserError("You cannot create a new revision while another revision is not in the 'released' state.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'New Revision',
            'res_model': 'document.revision',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_document_id': self.id,
                'default_revision_number': str(len(self.revision_ids) + 1),
                'default_previous_revision_ids': [(6, 0, self.revision_ids.ids)]
            }
        }
    # def action_new_revision(self):
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'New Revision',
    #         'res_model': 'document.revision',
    #         'view_mode': 'form',
    #         'target': 'new',
    #         'context': {'default_document_id': self.id}
    #     }

    # Added: Undo action for Document Admin
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