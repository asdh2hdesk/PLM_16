from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from logging import getLogger
import datetime
import json

_logger = getLogger(__name__)


class AdvancedRevisionHistory(models.Model):
    _name = 'advanced.revision.history'
    _description = 'Advanced Document Revision History'
    _order = 'revision_number desc, revision_date desc'

    name = fields.Char('Revision Title', required=True)
    revision_number = fields.Char('Revision Number', required=True)
    revision_format = fields.Char('Revision Format', required=True)
    revision_date = fields.Date('Revision Date', default=fields.Date.today, required=True)
    revised_by = fields.Many2one('res.users', string='Revised By', default=lambda self: self.env.user, required=True)
    revision_status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('approved', 'Approved')
    ], string='Revision Status', default='draft')

    # Generic reference fields to connect to any model
    res_model = fields.Char('Resource Model', required=True)
    res_id = fields.Integer('Resource ID', required=True)

    # Enhanced revision details
    revision_summary = fields.Text('Revision Summary')
    change_reason = fields.Selection([
        ('correction', 'Correction'),
        ('improvement', 'Improvement'),
        ('update', 'Update'),
        ('compliance', 'Compliance'),
        ('customer_request', 'Customer Request'),
        ('process_change', 'Process Change'),
        ('other', 'Other')
    ], string='Change Reason', required=True)

    # Field-level change tracking
    field_changes_ids = fields.One2many('advanced.revision.field.change', 'revision_id', string='Field Changes')

    # Approval tracking
    approval_required = fields.Boolean('Approval Required', default=True)
    approved_by = fields.Many2one('res.users', string='Approved By')
    approval_date = fields.Date('Approval Date')
    approval_comment = fields.Text('Approval Comment')

    # Document state before and after revision
    previous_state = fields.Char('Previous State')
    new_state = fields.Char('New State')

    # Revision metadata
    is_major_revision = fields.Boolean('Major Revision', default=False)
    affects_quality = fields.Boolean('Affects Quality', default=False)
    affects_safety = fields.Boolean('Affects Safety', default=False)
    affects_cost = fields.Boolean('Affects Cost', default=False)

    @api.model
    def create(self, vals):
        # Auto-generate revision format if not provided
        if not vals.get('revision_format'):
            vals['revision_format'] = f"REV-{vals.get('revision_number', '0')}"
        return super(AdvancedRevisionHistory, self).create(vals)

    def action_confirm_revision(self):
        """Confirm the revision"""
        for record in self:
            record.revision_status = 'confirmed'
            # Update the main document state
            main_document = self.env[record.res_model].browse(record.res_id)
            if hasattr(main_document, 'state'):
                main_document.write({'state': 'draft'})

    def action_approve_revision(self):
        """Approve the revision"""
        for record in self:
            record.revision_status = 'approved'
            record.approved_by = self.env.user
            record.approval_date = fields.Date.today()

    def get_document_reference(self):
        """Get the referenced document"""
        return self.env[self.res_model].browse(self.res_id)

    def action_view_field_changes(self):
        """Open field changes for this revision"""
        return {
            'name': _('Field Changes'),
            'type': 'ir.actions.act_window',
            'res_model': 'advanced.revision.field.change',
            'view_mode': 'tree,form',
            'domain': [('revision_id', '=', self.id)],
            'context': {'default_revision_id': self.id},
        }


class AdvancedRevisionFieldChange(models.Model):
    _name = 'advanced.revision.field.change'
    _description = 'Revision Field Change Details'
    _order = 'sequence, id'

    sequence = fields.Integer('Sequence', default=10)
    revision_id = fields.Many2one('advanced.revision.history', string='Revision', required=True, ondelete='cascade')

    field_name = fields.Char('Field Name', required=True)
    field_label = fields.Char('Field Label', required=True)
    field_type = fields.Selection([
        ('char', 'Text'),
        ('text', 'Long Text'),
        ('integer', 'Integer'),
        ('float', 'Float'),
        ('boolean', 'Boolean'),
        ('date', 'Date'),
        ('datetime', 'DateTime'),
        ('selection', 'Selection'),
        ('many2one', 'Many2One'),
        ('many2many', 'Many2Many'),
        ('one2many', 'One2Many'),
        ('binary', 'Binary'),
        ('html', 'HTML')
    ], string='Field Type', required=True)

    old_value = fields.Text('Previous Value')
    old_value_display = fields.Text('Previous Value (Display)')
    new_value = fields.Text('New Value')
    new_value_display = fields.Text('New Value (Display)')
    change_type = fields.Selection([
        ('added', 'Added'),
        ('modified', 'Modified'),
        ('removed', 'Removed')
    ], string='Change Type', required=True)

    change_description = fields.Text('Change Description')
    impact_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Impact Level', default='medium')

    # Add nesting level for better view formatting
    nesting_level = fields.Integer('Nesting Level', compute='_compute_nesting_level', store=True)
    is_nested_change = fields.Boolean('Is Nested Change', compute='_compute_nesting_level', store=True)
    is_deep_nested = fields.Boolean('Is Deep Nested Change', compute='_compute_nesting_level', store=True)

    @api.depends('field_name')
    def _compute_nesting_level(self):
        for record in self:
            if record.field_name:
                level = record.field_name.count('.')
                record.nesting_level = level
                record.is_nested_change = level > 0
                record.is_deep_nested = level > 1
            else:
                record.nesting_level = 0
                record.is_nested_change = False
                record.is_deep_nested = False

    @api.model
    def create(self, vals):
        # Auto-generate change description if not provided
        if not vals.get('change_description'):
            change_type = vals.get('change_type', 'modified')
            field_label = vals.get('field_label', '')
            old_display = vals.get('old_value_display', '')
            new_display = vals.get('new_value_display', '')

            if change_type == 'added':
                vals['change_description'] = f"Added new field: {field_label} = {new_display}"
            elif change_type == 'removed':
                vals['change_description'] = f"Removed field: {field_label} (was: {old_display})"
            else:
                vals['change_description'] = f"Modified {field_label}: '{old_display}' → '{new_display}'"

        return super(AdvancedRevisionFieldChange, self).create(vals)


class AdvancedRevisionHistoryMixin(models.AbstractModel):
    _name = 'advanced.revision.history.mixin'
    _description = 'Advanced Revision History Mixin'

    # Add search method for revision_history_ids
    def _search_revision_history_ids(self, operator, value):
        # This search method allows Odoo to find records by revision history
        if operator in ('=', 'in'):
            revision_records = self.env['advanced.revision.history'].search([
                ('res_model', '=', self._name),
                ('res_id', operator, value)
            ])
            return [('id', 'in', revision_records.mapped('res_id'))]
        else:
            return [('id', '=', 0)]

    # Revision tracking fields
    revision_history_ids = fields.One2many(
        'advanced.revision.history',
        compute='_compute_revision_history_ids',
        string='Revision History',
        search='_search_revision_history_ids',
    )

    current_revision_number = fields.Char('Current Revision', default='0', tracking=True)
    current_revision_format = fields.Char('Current Revision Format', compute='_compute_revision_format', store=True)
    revision_date = fields.Date('Revision Date', default=fields.Date.today, tracking=True)

    # Revision workflow
    revision_state = fields.Selection([
        ('draft', 'Draft'),
        ('under_revision', 'Under Revision'),
        ('revision_pending_approval', 'Revision Pending Approval'),
        ('revision_approved', 'Revision Approved')
    ], string='Revision State', default='draft', tracking=True)

    # Revision metadata
    total_revisions = fields.Integer('Total Revisions', compute='_compute_total_revisions', store=True)
    last_revision_date = fields.Date('Last Revision Date', compute='_compute_last_revision_date', store=True)
    last_revised_by = fields.Many2one('res.users', 'Last Revised By', compute='_compute_last_revised_by', store=True)

    # Revision button visibility
    show_revision_button = fields.Boolean('Show Revision Button', compute='_compute_show_revision_button')

    # Fields to exclude from change tracking
    _revision_exclude_fields = ['write_date', 'write_uid', '__last_update', 'activity_ids', 'message_ids']

    def _create_cross_model_change_records(self, target_record, old_values, new_values, change_context):
        """Create change records for cross-model updates"""
        changes = []

        # Get field labels from target model
        target_fields = target_record._fields

        for field_name, new_value in new_values.items():
            if field_name in ['operations_id']:  # Skip parent relations
                continue

            field_obj = target_fields.get(field_name)
            if not field_obj:
                continue

            old_value = old_values.get(field_name)

            # Determine change type
            change_type = 'modified'
            if field_name not in old_values:
                change_type = 'added'
            elif new_value is None or new_value is False:
                change_type = 'removed'

            # Skip if values are the same
            if old_value == new_value and change_type == 'modified':
                continue

            # Get display values
            old_display = self._get_cross_model_display_value(target_record, field_name, old_value)
            new_display = self._get_cross_model_display_value(target_record, field_name, new_value)

            changes.append({
                'field_name': f"cross_model.{target_record._name}.{field_name}",
                'field_label': f"PFMEA → {field_obj.string}",
                'field_type': field_obj.type,
                'old_value': str(old_value) if old_value is not None else '',
                'old_value_display': old_display,
                'new_value': str(new_value) if new_value is not None else '',
                'new_value_display': new_display,
                'change_type': change_type,
                'change_description': f"Updated from Process Flow ({change_context}): {field_obj.string} changed from '{old_display}' to '{new_display}'",
            })

        return changes

    def _get_cross_model_display_value(self, record, field_name, value):
        """Get display value for cross-model field tracking"""
        if value is None or value is False:
            return ''

        field_obj = record._fields.get(field_name)
        if not field_obj:
            return str(value)

        try:
            if field_obj.type == 'many2one':
                if isinstance(value, int):
                    related_record = self.env[field_obj.comodel_name].browse(value)
                    return related_record.display_name if related_record.exists() else f'ID:{value}'
                elif hasattr(value, 'display_name'):
                    return value.display_name
                return str(value)
            elif field_obj.type == 'selection':
                if hasattr(field_obj, 'selection'):
                    selection_dict = dict(field_obj.selection)
                    return selection_dict.get(value, str(value))
                return str(value)
            elif field_obj.type == 'boolean':
                return 'Yes' if value else 'No'
            else:
                return str(value)
        except Exception as e:
            return str(value)

    def _create_cross_model_revision_entries(self, updated_records_data, sync_type):
        """Create revision entries for cross-model synchronization"""

        # Create revision for source model (Process Flow)
        if hasattr(self, 'create_revision_entry'):
            source_revision_data = {
                'name': f'Cross-Model Sync: Updated PFMEA',
                'summary': f'Synchronized data to PFMEA models. Updated {len(updated_records_data)} PFMEA record(s).',
                'change_reason': 'process_change',
                'is_major_revision': False,
                'affects_quality': True,
                'affects_safety': False,
                'affects_cost': False,
            }

            # Collect all changes for source revision
            all_source_changes = []
            for pfmea_record, changes in updated_records_data:
                all_source_changes.extend(changes)

            if all_source_changes:  # Only create revision if there are actual changes
                self.create_revision_entry(source_revision_data, all_source_changes)

        # Create revision entries for target models (PFMEA records)
        for pfmea_record, changes in updated_records_data:
            if hasattr(pfmea_record, 'create_revision_entry'):
                target_revision_data = {
                    'name': f'Updated from Process Flow',
                    'summary': f'Data synchronized from Process Flow: {self.display_name}. {len(changes)} field(s) updated.',
                    'change_reason': 'update',
                    'is_major_revision': False,
                    'affects_quality': True,
                    'affects_safety': False,
                    'affects_cost': False,
                }

                pfmea_record.create_revision_entry(target_revision_data, changes)
    @api.depends('current_revision_number')
    def _compute_revision_format(self):
        for record in self:
            record.current_revision_format = f"REV-{record.current_revision_number or '0'}"

    @api.depends('revision_history_ids')
    def _compute_revision_history_ids(self):
        for record in self:
            record.revision_history_ids = self.env['advanced.revision.history'].search([
                ('res_model', '=', self._name),
                ('res_id', '=', record.id)
            ], order='revision_number desc, id desc')

    @api.depends('revision_history_ids')
    def _compute_total_revisions(self):
        for record in self:
            record.total_revisions = len(record.revision_history_ids)

    @api.depends('revision_history_ids.revision_date')
    def _compute_last_revision_date(self):
        for record in self:
            last_revision = record.revision_history_ids.sorted('revision_date', reverse=True)[:1]
            record.last_revision_date = last_revision.revision_date if last_revision else False

    @api.depends('revision_history_ids.revised_by')
    def _compute_last_revised_by(self):
        for record in self:
            last_revision = record.revision_history_ids.sorted('revision_date', reverse=True)[:1]
            record.last_revised_by = last_revision.revised_by if last_revision else False

    @api.depends('final_status', 'state')
    def _compute_show_revision_button(self):
        for record in self:
            # Show revision button only when document is approved
            record.show_revision_button = (
                    hasattr(record, 'final_status') and record.final_status == 'approved' and
                    hasattr(record, 'state') and record.state == 'confirm'
            )

    def action_start_revision(self):
        """Start a new revision process"""
        self.ensure_one()

        # Check if document is approved
        # if not self.show_revision_button:
        #     raise ValidationError(_("Revision can only be started on approved documents."))

        # Create revision wizard
        return {
            'name': _('Start Document Revision'),
            'type': 'ir.actions.act_window',
            'res_model': 'advanced.revision.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_current_revision': self.current_revision_number,
                'default_document_name': self.display_name,
            }
        }

    def action_confirm_revision(self):
        """Confirm the current revision"""
        self.ensure_one()
        if self.revision_state == 'under_revision':
            self.revision_state = 'revision_pending_approval'

    def action_approve_revision(self):
        """Approve the current revision"""
        self.ensure_one()
        if self.revision_state == 'revision_pending_approval':
            self.revision_state = 'revision_approved'
            # Reset to draft state for further editing
            if hasattr(self, 'state'):
                self.state = 'draft'

    def _get_field_display_value(self, field_name, value):
        """Get human-readable display value for a field"""
        if value is None or value is False:
            return ''

        field_obj = self._fields.get(field_name)
        if not field_obj:
            return str(value)

    def _convert_value_for_storage(self, field_obj, value):
        """Convert field value to a clean string for storage"""
        if value is None or value is False:
            return ''

        try:
            if field_obj.type == 'many2one':
                if isinstance(value, int):
                    record = self.env[field_obj.comodel_name].browse(value)
                    return f"ID:{value}" if record.exists() else f"ID:{value} (deleted)"
                elif hasattr(value, 'id'):
                    return f"ID:{value.id}"
                return str(value)
            elif field_obj.type == 'many2many':
                if isinstance(value, (list, tuple)):
                    if value and isinstance(value[0], (list, tuple)):
                        # Handle command format
                        ids = []
                        for cmd in value:
                            if len(cmd) >= 2 and cmd[0] in [4, 6]:  # Link or Replace
                                if cmd[0] == 4:
                                    ids.append(cmd[1])
                                elif cmd[0] == 6 and len(cmd) > 2:
                                    ids.extend(cmd[2])
                        return f"IDs:{ids}"
                    else:
                        return f"IDs:{list(value)}"
                elif hasattr(value, 'ids'):
                    return f"IDs:{value.ids}"
                return str(value)
            elif field_obj.type == 'one2many':
                if isinstance(value, (list, tuple)):
                    if value and isinstance(value[0], (list, tuple)):
                        # Handle command format - just store count
                        return f"Commands:{len(value)}"
                    else:
                        return f"Records:{len(value)}"
                elif hasattr(value, '__len__'):
                    return f"Records:{len(value)}"
                return str(value)
            elif field_obj.type in ['date', 'datetime']:
                if hasattr(value, 'strftime'):
                    return value.strftime('%Y-%m-%d %H:%M:%S') if field_obj.type == 'datetime' else value.strftime(
                        '%Y-%m-%d')
                return str(value)
            else:
                return str(value)
        except Exception as e:
            _logger.warning(f"Error converting value for storage - field {field_obj.name}: {str(e)}")
            return str(value)

        try:
            if field_obj.type == 'many2one':
                if isinstance(value, int):
                    record = self.env[field_obj.comodel_name].browse(value)
                    return record.display_name if record.exists() else ''
                elif hasattr(value, 'display_name'):
                    return value.display_name
                return str(value)
            elif field_obj.type == 'many2many':
                if isinstance(value, (list, tuple)):
                    records = self.env[field_obj.comodel_name].browse(value)
                    return ', '.join(records.mapped('display_name'))
                elif hasattr(value, 'mapped'):
                    return ', '.join(value.mapped('display_name'))
                return str(value)
            elif field_obj.type == 'one2many':
                if isinstance(value, (list, tuple)):
                    # Handle command lists like [[1, 1, {...}], [4, 2, False]]
                    if value and isinstance(value[0], (list, tuple)):
                        count = 0
                        for cmd in value:
                            if len(cmd) >= 1:
                                cmd_type = cmd[0]
                                if cmd_type in [0, 1, 4]:  # Create, Update, Link commands
                                    count += 1
                                elif cmd_type == 2:  # Delete command
                                    count -= 1
                                elif cmd_type == 5:  # Clear all
                                    count = 0
                                elif cmd_type == 6:  # Replace all
                                    if len(cmd) > 2 and isinstance(cmd[2], list):
                                        count = len(cmd[2])
                        return f'{max(0, count)} records'
                    else:
                        return f'{len(value)} records'
                elif hasattr(value, '__len__'):
                    return f'{len(value)} records'
                elif hasattr(value, 'mapped'):
                    return f'{len(value)} records'
                return str(value)
            elif field_obj.type == 'selection':
                selection_dict = dict(field_obj.selection)
                return selection_dict.get(value, str(value))
            elif field_obj.type == 'date':
                if isinstance(value, str):
                    return value
                return value.strftime('%Y-%m-%d') if value else ''
            elif field_obj.type == 'datetime':
                if isinstance(value, str):
                    return value
                return value.strftime('%Y-%m-%d %H:%M:%S') if value else ''
            elif field_obj.type == 'boolean':
                return 'Yes' if value else 'No'
            else:
                return str(value)
        except Exception as e:
            _logger.warning(f"Error getting display value for field {field_name}: {str(e)}")
            return str(value)

    def _should_track_field(self, field_name):
        """Determine if a field should be tracked for changes"""
        # Exclude system fields and specified fields
        if field_name.startswith('_') or field_name in self._revision_exclude_fields:
            return False

        # Only track stored fields
        field_obj = self._fields.get(field_name)
        if not field_obj or not field_obj.store:
            return False

        # Skip computed fields without store
        if field_obj.compute and not field_obj.store:
            return False

        return True

    def track_field_changes(self, old_values, new_values):
        """Track field changes for revision history"""
        changes = []

        # Get all fields that have changed
        all_changed_fields = set(old_values.keys()) | set(new_values.keys())

        for field_name in all_changed_fields:
            if not self._should_track_field(field_name):
                continue

            field_obj = self._fields.get(field_name)
            if not field_obj:
                continue

            old_value = old_values.get(field_name)
            new_value = new_values.get(field_name)

            # Skip if values are the same
            if old_value == new_value:
                continue

            # Handle different change types
            change_type = 'modified'
            if field_name not in old_values:
                change_type = 'added'
            elif field_name not in new_values:
                change_type = 'removed'

            # Get display values
            old_display = self._get_field_display_value(field_name, old_value)
            new_display = self._get_field_display_value(field_name, new_value)

            # Convert values to strings for storage
            old_value_str = self._convert_value_for_storage(field_obj, old_value)
            new_value_str = self._convert_value_for_storage(field_obj, new_value)

            changes.append({
                'field_name': field_name,
                'field_label': field_obj.string or field_name,
                'field_type': field_obj.type,
                'old_value': old_value_str,
                'old_value_display': old_display,
                'new_value': new_value_str,
                'new_value_display': new_display,
                'change_type': change_type,
            })

        return changes

    def _track_nested_o2m_changes(self, parent_model, nested_field_name, old_nested_data, new_nested_commands, prefix):
        """Track changes in nested One2Many fields (child's child)"""
        changes = []

        nested_field_obj = parent_model._fields.get(nested_field_name)
        if not nested_field_obj or nested_field_obj.type != 'one2many':
            return changes

        nested_comodel = self.env[nested_field_obj.comodel_name]
        current_prefix = f"{prefix}.{nested_field_name}"

        # Process nested commands
        for command in new_nested_commands:
            if not isinstance(command, (list, tuple)) or len(command) < 3:
                continue

            cmd_type = command[0]

            if cmd_type == 1:  # Update existing nested record
                record_id = command[1]
                update_values = command[2]

                if record_id in old_nested_data and update_values:
                    old_nested_record = old_nested_data[record_id]
                    old_nested_fields = old_nested_record.get('fields', {})
                    old_nested_nested_o2m = old_nested_record.get('nested_o2m', {})

                    # Track direct field changes in nested record
                    for nested_sub_field_name, new_value in update_values.items():
                        nested_sub_field_obj = nested_comodel._fields.get(nested_sub_field_name)
                        if not nested_sub_field_obj:
                            continue

                        if nested_sub_field_obj.type == 'one2many':
                            # Handle even deeper nesting (third level)
                            old_deeper_data = old_nested_nested_o2m.get(nested_sub_field_name, {})
                            deeper_changes = self._track_nested_o2m_changes(
                                nested_comodel, nested_sub_field_name, old_deeper_data, new_value, current_prefix
                            )
                            changes.extend(deeper_changes)
                        else:
                            old_value = old_nested_fields.get(nested_sub_field_name)

                            if old_value != new_value:
                                old_display = self._get_field_display_value_for_comodel(nested_comodel,
                                                                                        nested_sub_field_name,
                                                                                        old_value)
                                new_display = self._get_field_display_value_for_comodel(nested_comodel,
                                                                                        nested_sub_field_name,
                                                                                        new_value)

                                changes.append({
                                    'field_name': f"{current_prefix}.{nested_sub_field_name}",
                                    'field_label': f"{nested_field_obj.string} → {nested_sub_field_obj.string}",
                                    'field_type': nested_sub_field_obj.type,
                                    'old_value': str(old_value) if old_value is not None else '',
                                    'old_value_display': old_display,
                                    'new_value': str(new_value) if new_value is not None else '',
                                    'new_value_display': new_display,
                                    'change_type': 'modified',
                                })

            elif cmd_type == 0:  # Create new nested record
                create_values = command[2]
                if create_values:
                    for nested_sub_field_name, new_value in create_values.items():
                        nested_sub_field_obj = nested_comodel._fields.get(nested_sub_field_name)
                        if nested_sub_field_obj and new_value is not None:
                            if nested_sub_field_obj.type == 'one2many':
                                # Handle nested One2Many in new records
                                deeper_changes = self._track_nested_o2m_changes(
                                    nested_comodel, nested_sub_field_name, {}, new_value, current_prefix
                                )
                                changes.extend(deeper_changes)
                            else:
                                new_display = self._get_field_display_value_for_comodel(nested_comodel,
                                                                                        nested_sub_field_name,
                                                                                        new_value)

                                changes.append({
                                    'field_name': f"{current_prefix}.{nested_sub_field_name}",
                                    'field_label': f"{nested_field_obj.string} → {nested_sub_field_obj.string}",
                                    'field_type': nested_sub_field_obj.type,
                                    'old_value': '',
                                    'old_value_display': '',
                                    'new_value': str(new_value),
                                    'new_value_display': new_display,
                                    'change_type': 'added',
                                })

            elif cmd_type == 2:  # Delete nested record
                record_id = command[1]
                if record_id in old_nested_data:
                    old_nested_record = old_nested_data[record_id]
                    old_nested_fields = old_nested_record.get('fields', {})
                    old_nested_nested_o2m = old_nested_record.get('nested_o2m', {})

                    # Track deletion of direct fields in nested record
                    for nested_sub_field_name, old_value in old_nested_fields.items():
                        nested_sub_field_obj = nested_comodel._fields.get(nested_sub_field_name)
                        if nested_sub_field_obj and old_value is not None:
                            old_display = self._get_field_display_value_for_comodel(nested_comodel,
                                                                                    nested_sub_field_name, old_value)

                            changes.append({
                                'field_name': f"{current_prefix}.{nested_sub_field_name}",
                                'field_label': f"{nested_field_obj.string} → {nested_sub_field_obj.string}",
                                'field_type': nested_sub_field_obj.type,
                                'old_value': str(old_value),
                                'old_value_display': old_display,
                                'new_value': '',
                                'new_value_display': '',
                                'change_type': 'removed',
                            })

                    # Track deletion of even deeper nested records
                    for deeper_field_name, deeper_data in old_nested_nested_o2m.items():
                        for deeper_record_id, deeper_record_data in deeper_data.items():
                            deeper_fields = deeper_record_data.get('fields', {})
                            for deeper_sub_field, old_value in deeper_fields.items():
                                deeper_field_obj = nested_comodel._fields.get(deeper_field_name)
                                if deeper_field_obj and old_value is not None:
                                    deeper_comodel = self.env[deeper_field_obj.comodel_name]
                                    deeper_sub_field_obj = deeper_comodel._fields.get(deeper_sub_field)
                                    if deeper_sub_field_obj:
                                        old_display = self._get_field_display_value_for_comodel(deeper_comodel,
                                                                                                deeper_sub_field,
                                                                                                old_value)

                                        changes.append({
                                            'field_name': f"{current_prefix}.{deeper_field_name}.{deeper_sub_field}",
                                            'field_label': f"{nested_field_obj.string} → {deeper_field_obj.string} → {deeper_sub_field_obj.string}",
                                            'field_type': deeper_sub_field_obj.type,
                                            'old_value': str(old_value),
                                            'old_value_display': old_display,
                                            'new_value': '',
                                            'new_value_display': '',
                                            'change_type': 'removed',
                                        })

        return changes

    def create_revision_entry(self, revision_data, field_changes=None):
        """Create a new revision history entry"""
        # Increment revision number
        try:
            current_rev = int(self.current_revision_number or '0')
            new_revision_number = str(current_rev + 1)
        except ValueError:
            new_revision_number = '1'

        # Create revision history record
        revision_vals = {
            'name': revision_data.get('name', f'Revision {new_revision_number}'),
            'revision_number': new_revision_number,
            'revision_date': revision_data.get('revision_date', fields.Date.today()),
            'revised_by': self.env.user.id,
            'res_model': self._name,
            'res_id': self.id,
            'revision_summary': revision_data.get('summary', ''),
            'change_reason': revision_data.get('change_reason', 'other'),
            'is_major_revision': revision_data.get('is_major_revision', False),
            'affects_quality': revision_data.get('affects_quality', False),
            'affects_safety': revision_data.get('affects_safety', False),
            'affects_cost': revision_data.get('affects_cost', False),
        }

        revision = self.env['advanced.revision.history'].create(revision_vals)

        # Create field change records
        if field_changes:
            for change in field_changes:
                change['revision_id'] = revision.id
                self.env['advanced.revision.field.change'].create(change)

        # Update current revision number
        self.write({
            'current_revision_number': new_revision_number,
            'revision_date': revision_data.get('revision_date', fields.Date.today()),
            'revision_state': 'under_revision'
        })

        return revision

    @api.model
    def create(self, vals):
        """Override create to set initial revision"""
        if 'current_revision_number' not in vals:
            vals['current_revision_number'] = '0'
        if 'revision_date' not in vals:
            vals['revision_date'] = fields.Date.today()

        record = super(AdvancedRevisionHistoryMixin, self).create(vals)

        # Create initial revision history entry
        self.env['advanced.revision.history'].create({
            'name': 'Initial Version',
            'revision_number': '0',
            'revision_date': record.revision_date,
            'revised_by': self.env.user.id,
            'res_model': record._name,
            'res_id': record.id,
            'revision_summary': 'Initial document creation',
            'change_reason': 'other',
            'revision_status': 'confirmed',
        })

        return record

    def write(self, vals):
        """Override write to track changes for revision"""
        # Store old values for comparison - get fresh data from database
        old_values_dict = {}
        old_o2m_values_dict = {}

        for record in self:
            # Re-read the record from database to get current values
            fresh_record = self.env[self._name].browse(record.id)
            old_values = {}
            old_o2m_values = {}

            for field_name in vals.keys():
                if self._should_track_field(field_name):
                    field_obj = self._fields.get(field_name)
                    current_value = getattr(fresh_record, field_name, None)
                    old_values[field_name] = current_value

                    # For One2Many fields, store detailed record data
                    if field_obj and field_obj.type == 'one2many' and current_value:
                        old_o2m_values[field_name] = self._extract_o2m_field_values(current_value)

            old_values_dict[record.id] = old_values
            old_o2m_values_dict[record.id] = old_o2m_values

        # Perform the write operation
        result = super(AdvancedRevisionHistoryMixin, self).write(vals)

        # Track changes for records under revision
        for record in self:
            if record.revision_state == 'under_revision':
                old_values = old_values_dict.get(record.id, {})
                old_o2m_values = old_o2m_values_dict.get(record.id, {})

                # Track regular field changes
                changed_vals = {}
                for field_name, new_value in vals.items():
                    if field_name in old_values:
                        field_obj = self._fields.get(field_name)
                        if field_obj and field_obj.type != 'one2many':
                            changed_vals[field_name] = new_value

                if changed_vals:
                    field_changes = record.track_field_changes(old_values, changed_vals)
                    if field_changes:
                        latest_revision = record.revision_history_ids.sorted('revision_number', reverse=True)[:1]
                        if latest_revision:
                            for change in field_changes:
                                change['revision_id'] = latest_revision.id
                                self.env['advanced.revision.field.change'].create(change)

                # Track One2Many field changes
                for field_name, new_commands in vals.items():
                    field_obj = self._fields.get(field_name)
                    if field_obj and field_obj.type == 'one2many' and self._should_track_field(field_name):
                        o2m_changes = record._track_o2m_changes(
                            field_name,
                            old_o2m_values.get(field_name, {}),
                            new_commands
                        )
                        if o2m_changes:
                            latest_revision = record.revision_history_ids.sorted('revision_number', reverse=True)[:1]
                            if latest_revision:
                                for change in o2m_changes:
                                    change['revision_id'] = latest_revision.id
                                    self.env['advanced.revision.field.change'].create(change)

        return result

    def _extract_o2m_field_values(self, o2m_records, prefix=""):
        """Extract field values from One2Many records for comparison, including nested O2M"""
        records_data = {}
        for record in o2m_records:
            record_fields = {}
            nested_o2m_data = {}

            for field_name, field_obj in record._fields.items():
                if field_obj.store and not field_name.startswith('_') and field_name not in ['id', 'create_date',
                                                                                             'write_date', 'create_uid',
                                                                                             'write_uid']:
                    try:
                        field_value = getattr(record, field_name, None)

                        if field_obj.type == 'one2many' and field_value:
                            # Handle nested One2Many recursively
                            nested_prefix = f"{prefix}.{field_name}" if prefix else field_name
                            nested_o2m_data[field_name] = self._extract_o2m_field_values(field_value, nested_prefix)
                        else:
                            record_fields[field_name] = field_value
                    except:
                        continue

            records_data[record.id] = {
                'fields': record_fields,
                'nested_o2m': nested_o2m_data
            }
        return records_data

    def _track_o2m_changes(self, field_name, old_records_data, new_commands, prefix=""):
        """Track changes in One2Many fields at record level, including nested O2M"""
        changes = []
        field_obj = self._fields.get(field_name)
        if not field_obj:
            return changes

        # Get the comodel to understand field structure
        comodel = self.env[field_obj.comodel_name]
        current_prefix = f"{prefix}.{field_name}" if prefix else field_name

        # Process each command
        for command in new_commands:
            if not isinstance(command, (list, tuple)) or len(command) < 3:
                continue

            cmd_type = command[0]

            if cmd_type == 1:  # Update existing record
                record_id = command[1]
                update_values = command[2]

                if record_id in old_records_data and update_values:
                    old_record_data = old_records_data[record_id]
                    old_fields = old_record_data.get('fields', {})
                    old_nested_o2m = old_record_data.get('nested_o2m', {})

                    # Track each direct field change in the updated record
                    for sub_field_name, new_value in update_values.items():
                        sub_field_obj = comodel._fields.get(sub_field_name)
                        if not sub_field_obj:
                            continue

                        if sub_field_obj.type == 'one2many':
                            # Handle nested One2Many changes
                            old_nested_data = old_nested_o2m.get(sub_field_name, {})
                            nested_changes = self._track_nested_o2m_changes(
                                comodel, sub_field_name, old_nested_data, new_value, current_prefix
                            )
                            changes.extend(nested_changes)
                        else:
                            # Handle direct field changes
                            old_value = old_fields.get(sub_field_name)

                            if old_value != new_value:
                                old_display = self._get_field_display_value_for_comodel(comodel, sub_field_name,
                                                                                        old_value)
                                new_display = self._get_field_display_value_for_comodel(comodel, sub_field_name,
                                                                                        new_value)

                                changes.append({
                                    'field_name': f"{current_prefix}.{sub_field_name}",
                                    'field_label': f"{field_obj.string} → {sub_field_obj.string}",
                                    'field_type': sub_field_obj.type,
                                    'old_value': str(old_value) if old_value is not None else '',
                                    'old_value_display': old_display,
                                    'new_value': str(new_value) if new_value is not None else '',
                                    'new_value_display': new_display,
                                    'change_type': 'modified',
                                })

            elif cmd_type == 0:  # Create new record
                create_values = command[2]
                if create_values:
                    for sub_field_name, new_value in create_values.items():
                        sub_field_obj = comodel._fields.get(sub_field_name)
                        if sub_field_obj and new_value is not None:
                            if sub_field_obj.type == 'one2many':
                                # Handle nested One2Many in new records
                                nested_changes = self._track_nested_o2m_changes(
                                    comodel, sub_field_name, {}, new_value, current_prefix
                                )
                                changes.extend(nested_changes)
                            else:
                                new_display = self._get_field_display_value_for_comodel(comodel, sub_field_name,
                                                                                        new_value)

                                changes.append({
                                    'field_name': f"{current_prefix}.{sub_field_name}",
                                    'field_label': f"{field_obj.string} → {sub_field_obj.string}",
                                    'field_type': sub_field_obj.type,
                                    'old_value': '',
                                    'old_value_display': '',
                                    'new_value': str(new_value),
                                    'new_value_display': new_display,
                                    'change_type': 'added',
                                })

            elif cmd_type == 2:  # Delete record
                record_id = command[1]
                if record_id in old_records_data:
                    old_record_data = old_records_data[record_id]
                    old_fields = old_record_data.get('fields', {})
                    old_nested_o2m = old_record_data.get('nested_o2m', {})

                    # Track deletion of direct fields
                    for sub_field_name, old_value in old_fields.items():
                        sub_field_obj = comodel._fields.get(sub_field_name)
                        if sub_field_obj and old_value is not None:
                            old_display = self._get_field_display_value_for_comodel(comodel, sub_field_name, old_value)

                            changes.append({
                                'field_name': f"{current_prefix}.{sub_field_name}",
                                'field_label': f"{field_obj.string} → {sub_field_obj.string}",
                                'field_type': sub_field_obj.type,
                                'old_value': str(old_value),
                                'old_value_display': old_display,
                                'new_value': '',
                                'new_value_display': '',
                                'change_type': 'removed',
                            })

                    # Track deletion of nested One2Many records
                    for nested_field_name, nested_data in old_nested_o2m.items():
                        for nested_record_id, nested_record_data in nested_data.items():
                            nested_fields = nested_record_data.get('fields', {})
                            for nested_sub_field, old_value in nested_fields.items():
                                nested_field_obj = comodel._fields.get(nested_field_name)
                                if nested_field_obj and old_value is not None:
                                    nested_comodel = self.env[nested_field_obj.comodel_name]
                                    nested_sub_field_obj = nested_comodel._fields.get(nested_sub_field)
                                    if nested_sub_field_obj:
                                        old_display = self._get_field_display_value_for_comodel(nested_comodel,
                                                                                                nested_sub_field,
                                                                                                old_value)

                                        changes.append({
                                            'field_name': f"{current_prefix}.{nested_field_name}.{nested_sub_field}",
                                            'field_label': f"{field_obj.string} → {nested_field_obj.string} → {nested_sub_field_obj.string}",
                                            'field_type': nested_sub_field_obj.type,
                                            'old_value': str(old_value),
                                            'old_value_display': old_display,
                                            'new_value': '',
                                            'new_value_display': '',
                                            'change_type': 'removed',
                                        })

        return changes

    def _get_field_display_value_for_comodel(self, comodel, field_name, value):
        """Get display value for a field in a comodel (for One2Many tracking)"""
        if value is None or value is False:
            return ''

        field_obj = comodel._fields.get(field_name)
        if not field_obj:
            return str(value)

        try:
            if field_obj.type == 'many2one':
                if isinstance(value, int):
                    record = self.env[field_obj.comodel_name].browse(value)
                    return record.display_name if record.exists() else f'ID:{value}'
                elif hasattr(value, 'display_name'):
                    return value.display_name
                return str(value)
            elif field_obj.type == 'selection':
                selection_dict = dict(field_obj.selection)
                return selection_dict.get(value, str(value))
            elif field_obj.type == 'date':
                if hasattr(value, 'strftime'):
                    return value.strftime('%Y-%m-%d')
                return str(value)
            elif field_obj.type == 'datetime':
                if hasattr(value, 'strftime'):
                    return value.strftime('%Y-%m-%d %H:%M:%S')
                return str(value)
            elif field_obj.type == 'boolean':
                return 'Yes' if value else 'No'
            else:
                return str(value)
        except Exception:
            return str(value)

    def action_view_revisions(self):
        """Open revision history for this document"""
        return {
            'name': _('Revision History'),
            'type': 'ir.actions.act_window',
            'res_model': 'advanced.revision.history',
            'view_mode': 'tree,form',
            'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }


class AdvancedRevisionWizard(models.TransientModel):
    _name = 'advanced.revision.wizard'
    _description = 'Advanced Document Revision Wizard'

    res_model = fields.Char('Resource Model', required=True)
    res_id = fields.Integer('Resource ID', required=True)
    current_revision = fields.Char('Current Revision', readonly=True)
    document_name = fields.Char('Document Name', readonly=True)

    # Revision details
    revision_name = fields.Char('Revision Title', required=True)
    revision_summary = fields.Text('Revision Summary', required=True)
    change_reason = fields.Selection([
        ('correction', 'Correction'),
        ('improvement', 'Improvement'),
        ('update', 'Update'),
        ('compliance', 'Compliance'),
        ('customer_request', 'Customer Request'),
        ('process_change', 'Process Change'),
        ('other', 'Other')
    ], string='Change Reason', required=True)

    # Impact assessment
    is_major_revision = fields.Boolean('Major Revision')
    affects_quality = fields.Boolean('Affects Quality')
    affects_safety = fields.Boolean('Affects Safety')
    affects_cost = fields.Boolean('Affects Cost')

    # Confirmation
    confirm_revision = fields.Boolean('I confirm this revision', required=True)

    def action_create_revision(self):
        """Create the revision and update document state"""
        if not self.confirm_revision:
            raise ValidationError(_("Please confirm the revision before proceeding."))

        # Get the document
        document = self.env[self.res_model].browse(self.res_id)

        # Create revision data
        revision_data = {
            'name': self.revision_name,
            'summary': self.revision_summary,
            'change_reason': self.change_reason,
            'is_major_revision': self.is_major_revision,
            'affects_quality': self.affects_quality,
            'affects_safety': self.affects_safety,
            'affects_cost': self.affects_cost,
            'revision_date': fields.Date.today(),
        }

        # Create revision entry
        document.create_revision_entry(revision_data)

        # Update document state to draft
        if hasattr(document, 'state'):
            document.state = 'draft'

        # Reset approval status
        if hasattr(document, 'final_status'):
            document.final_status = 'draft'

        # Reset approver comments
        if hasattr(document, 'iatf_members_ids'):
            for member in document.iatf_members_ids:
                member.write({
                    'approval_status': False,
                    'comment': False,
                    'date_approved_rejected': False
                })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Revision Created"),
                'message': _("Document revision has been created successfully. The document is now in draft state."),
                'sticky': False,
                'type': 'success',
            }
        }