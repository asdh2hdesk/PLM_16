from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DocumentControlECN(models.Model):
    _inherit = 'document.control'

    ecn_count = fields.Integer(
        string='ECN Count',
        compute='_compute_ecn_count',
        store=False  # Make sure it's computed each time
    )

    def _compute_ecn_count(self):
        """Compute the number of ECNs related to this document"""
        for record in self:
            if record.part_number_id and record.customer_name:
                # Ensure we're using the correct field references
                part_id = record.part_number_id.product_tmpl_id.id if hasattr(record.part_number_id, 'product_tmpl_id') else record.part_number_id.id
                record.ecn_count = self.env['asd.ecn'].search_count([
                    ('part_id', '=', part_id),
                    ('partner_id', '=', record.customer_name.id)
                ])
            else:
                record.ecn_count = 0

    def action_create_ecn(self):
        """Create ECN from Document Control"""
        self.ensure_one()

        # Validation
        if not self.part_number_id:
            raise UserError(_("Please select a Part Number before creating ECN."))
        if not self.customer_name:
            raise UserError(_("Please select a Customer Name before creating ECN."))

        # Get the correct part ID
        part_id = self.part_number_id.product_tmpl_id.id if hasattr(self.part_number_id, 'product_tmpl_id') else self.part_number_id.id

        # Create ECN record
        ecn_vals = {
            'part_id': part_id,
            'partner_id': self.customer_name.id,
            'document_control_id': self.id,
            'description': self.name or '',
        }

        ecn = self.env['asd.ecn'].create(ecn_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Engineering Change Note'),
            'res_model': 'asd.ecn',
            'res_id': ecn.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_ecns(self):
        """View all ECNs related to this document"""
        self.ensure_one()

        # Get the correct part ID
        part_id = self.part_number_id.product_tmpl_id.id if hasattr(self.part_number_id, 'product_tmpl_id') else self.part_number_id.id

        action = self.env.ref('ecn.action_asd_ecn').read()[0]
        action['domain'] = [
            ('part_id', '=', part_id),
            ('partner_id', '=', self.customer_name.id)
        ]
        action['context'] = {
            'default_part_id': part_id,
            'default_partner_id': self.customer_name.id,
            'default_document_control_id': self.id,
        }

        if self.ecn_count == 1:
            ecn = self.env['asd.ecn'].search([
                ('part_id', '=', part_id),
                ('partner_id', '=', self.customer_name.id)
            ], limit=1)
            action['res_id'] = ecn.id
            action['view_mode'] = 'form'
            action['views'] = [(False, 'form')]

        return action