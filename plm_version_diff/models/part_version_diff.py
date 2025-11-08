from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import difflib
from datetime import datetime


class PartVersionDiff(models.Model):
    _name = 'part.version.diff'
    _description = 'Part Version Comparison'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Comparison Reference', compute='_compute_name', store=True)

    # Part A (From)
    part_a_id = fields.Many2one(
        'product.product',
        string='Part A (From)',
        required=True,
        domain=[('type', 'in', ['product', 'consu'])],
        tracking=True
    )
    part_a_name = fields.Char(related='part_a_id.name', string='Part A Name', readonly=True)
    part_a_default_code = fields.Char(related='part_a_id.default_code', string='Part A Code', readonly=True)

    # Part B (To)
    part_b_id = fields.Many2one(
        'product.product',
        string='Part B (To)',
        required=True,
        domain=[('type', 'in', ['product', 'consu'])],
        tracking=True
    )
    part_b_name = fields.Char(related='part_b_id.name', string='Part B Name', readonly=True)
    part_b_default_code = fields.Char(related='part_b_id.default_code', string='Part B Code', readonly=True)

    # Document Control Records
    document_a_id = fields.Many2one(
        'document.control',
        string='Document A',
        compute='_compute_documents',
        store=True
    )
    document_b_id = fields.Many2one(
        'document.control',
        string='Document B',
        compute='_compute_documents',
        store=True
    )

    # Comparison Type
    comparison_type = fields.Selection([
        ('all', 'All Differences'),
        ('bom', 'BOM Only'),
        ('documents', 'Documents Only'),
        ('revisions', 'Revisions Only'),
        ('files', 'Files Only'),
        ('technical', 'Technical Information Only')
    ], string='Comparison Type', default='all', required=True)

    # Results
    bom_differences = fields.Text(string='BOM Differences (JSON)')
    bom_differences_html = fields.Html(string='BOM Differences', compute='_compute_html_displays')

    document_differences = fields.Text(string='Document Differences (JSON)')
    document_differences_html = fields.Html(string='Document Differences', compute='_compute_html_displays')

    revision_differences = fields.Text(string='Revision Differences (JSON)')
    revision_differences_html = fields.Html(string='Revision Differences', compute='_compute_html_displays')

    file_differences = fields.Text(string='File Differences (JSON)')
    file_differences_html = fields.Html(string='File Differences', compute='_compute_html_displays')

    technical_differences = fields.Text(string='Technical Information Differences (JSON)')
    technical_differences_html = fields.Html(string='Technical Information Differences',
                                             compute='_compute_html_displays')

    # Summary Statistics
    total_bom_changes = fields.Integer(string='Total BOM Changes', compute='_compute_summary', store=True)
    bom_additions = fields.Integer(string='BOM Additions', compute='_compute_summary', store=True)
    bom_deletions = fields.Integer(string='BOM Deletions', compute='_compute_summary', store=True)
    bom_modifications = fields.Integer(string='BOM Modifications', compute='_compute_summary', store=True)

    total_file_changes = fields.Integer(string='Total File Changes', compute='_compute_summary', store=True)
    file_additions = fields.Integer(string='Files Added', compute='_compute_summary', store=True)
    file_deletions = fields.Integer(string='Files Removed', compute='_compute_summary', store=True)

    total_technical_changes = fields.Integer(string='Total Technical Changes', compute='_compute_summary', store=True)

    revision_count_a = fields.Integer(string='Part A Revisions', compute='_compute_summary', store=True)
    revision_count_b = fields.Integer(string='Part B Revisions', compute='_compute_summary', store=True)

    # Metadata
    compared_by = fields.Many2one('res.users', string='Compared By', default=lambda self: self.env.user, readonly=True)
    compared_date = fields.Datetime(string='Comparison Date', default=fields.Datetime.now, readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('compared', 'Compared'),
    ], string='Status', default='draft', tracking=True)

    notes = fields.Text(string='Notes')

    @api.depends('part_a_id', 'part_b_id')
    def _compute_name(self):
        for record in self:
            if record.part_a_id and record.part_b_id:
                record.name = f"Compare: {record.part_a_id.default_code or record.part_a_id.name} vs {record.part_b_id.default_code or record.part_b_id.name}"
            else:
                record.name = "New Comparison"

    @api.depends('part_a_id', 'part_b_id')
    def _compute_documents(self):
        for record in self:
            if record.part_a_id:
                doc_a = self.env['document.control'].search([
                    ('part_number_id', '=', record.part_a_id.id)
                ], limit=1)
                record.document_a_id = doc_a.id if doc_a else False
            else:
                record.document_a_id = False

            if record.part_b_id:
                doc_b = self.env['document.control'].search([
                    ('part_number_id', '=', record.part_b_id.id)
                ], limit=1)
                record.document_b_id = doc_b.id if doc_b else False
            else:
                record.document_b_id = False

    @api.depends('bom_differences', 'file_differences', 'revision_differences', 'technical_differences')
    def _compute_summary(self):
        for record in self:
            # BOM Summary
            if record.bom_differences:
                try:
                    bom_data = json.loads(record.bom_differences)
                    record.total_bom_changes = len(bom_data)
                    record.bom_additions = sum(1 for item in bom_data if item.get('change_type') == 'added')
                    record.bom_deletions = sum(1 for item in bom_data if item.get('change_type') == 'deleted')
                    record.bom_modifications = sum(1 for item in bom_data if item.get('change_type') == 'modified')
                except:
                    record.total_bom_changes = 0
                    record.bom_additions = 0
                    record.bom_deletions = 0
                    record.bom_modifications = 0
            else:
                record.total_bom_changes = 0
                record.bom_additions = 0
                record.bom_deletions = 0
                record.bom_modifications = 0

            # File Summary
            if record.file_differences:
                try:
                    file_data = json.loads(record.file_differences)
                    record.total_file_changes = len(file_data)
                    record.file_additions = sum(1 for item in file_data if item.get('change_type') == 'added')
                    record.file_deletions = sum(1 for item in file_data if item.get('change_type') == 'deleted')
                except:
                    record.total_file_changes = 0
                    record.file_additions = 0
                    record.file_deletions = 0
            else:
                record.total_file_changes = 0
                record.file_additions = 0
                record.file_deletions = 0

            if record.technical_differences:
                try:
                    tech_data = json.loads(record.technical_differences)
                    # Count fields that exist (not just modified ones)
                    record.total_technical_changes = len([
                        item for item in tech_data
                        if 'field' in item and not item.get('message')
                    ])
                except:
                    record.total_technical_changes = 0
            else:
                record.total_technical_changes = 0

            # Revision Counts
            if record.document_a_id:
                record.revision_count_a = len(record.document_a_id.revision_ids)
            else:
                record.revision_count_a = 0

            if record.document_b_id:
                record.revision_count_b = len(record.document_b_id.revision_ids)
            else:
                record.revision_count_b = 0

    @api.depends('bom_differences', 'document_differences', 'revision_differences', 'file_differences',
                 'technical_differences')
    def _compute_html_displays(self):
        for record in self:
            if record.bom_differences:
                record.bom_differences_html = record._generate_bom_html()
            else:
                record.bom_differences_html = "<p>No BOM comparison performed</p>"

            if record.document_differences:
                record.document_differences_html = record._generate_document_html()
            else:
                record.document_differences_html = "<p>No document comparison performed</p>"

            if record.revision_differences:
                record.revision_differences_html = record._generate_revision_html()
            else:
                record.revision_differences_html = "<p>No revision comparison performed</p>"

            if record.file_differences:
                record.file_differences_html = record._generate_file_html()
            else:
                record.file_differences_html = "<p>No file comparison performed</p>"

            if record.technical_differences:
                record.technical_differences_html = record._generate_technical_html()
            else:
                record.technical_differences_html = "<p>No technical information comparison performed</p>"

    def action_compare(self):
        """Execute the comparison"""
        self.ensure_one()

        if not self.part_a_id or not self.part_b_id:
            raise UserError(_("Please select both Part A and Part B to compare."))

        if self.part_a_id.id == self.part_b_id.id:
            raise UserError(_("Cannot compare a part with itself. Please select different parts."))

        # Perform comparisons based on type
        if self.comparison_type in ['all', 'bom']:
            self.bom_differences = json.dumps(self._compare_boms(), indent=2)

        if self.comparison_type in ['all', 'documents']:
            self.document_differences = json.dumps(self._compare_documents(), indent=2)

        if self.comparison_type in ['all', 'revisions']:
            self.revision_differences = json.dumps(self._compare_revisions(), indent=2)

        if self.comparison_type in ['all', 'files']:
            self.file_differences = json.dumps(self._compare_files(), indent=2)

        if self.comparison_type in ['all', 'technical']:
            self.technical_differences = json.dumps(self._compare_technical_info(), indent=2)

        self.state = 'compared'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'part.version.diff',
            'res_id': self.id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
        }

    def _compare_technical_info(self):
        """Compare technical information between two parts"""
        differences = []

        if not self.part_a_id or not self.part_b_id:
            return [{'message': 'Parts not selected'}]

        part_a = self.part_a_id
        part_b = self.part_b_id

        # Define technical fields to compare - these are on product.product model
        technical_fields = [
            ('tmp_material', 'Raw Material'),
            ('tmp_surface', 'Surface Finishing'),
            ('tmp_treatment', 'Thermal Treatment'),
            ('engineering_material', 'CAD Raw Material'),
            ('engineering_surface', 'CAD Surface Finishing'),
            ('engineering_treatment', 'CAD Thermal Treatment'),
        ]

        for field_name, label in technical_fields:
            # Get values from product.product
            val_a = getattr(part_a, field_name, False)
            val_b = getattr(part_b, field_name, False)

            # Convert Many2one to string representation
            if hasattr(val_a, 'name'):
                val_a_str = val_a.name
            else:
                val_a_str = str(val_a) if val_a else ''

            if hasattr(val_b, 'name'):
                val_b_str = val_b.name
            else:
                val_b_str = str(val_b) if val_b else ''

            # Add the field to show complete information
            differences.append({
                'field': label,
                'value_a': val_a_str,
                'value_b': val_b_str,
                'change_type': 'modified' if val_a_str != val_b_str else 'unchanged'
            })

        return differences

    def _compare_boms(self):
        """Compare BOMs between two parts"""
        differences = []

        # Get BOMs for both parts
        bom_a = self.env['mrp.bom'].search([('product_tmpl_id', '=', self.part_a_id.product_tmpl_id.id)], limit=1)
        bom_b = self.env['mrp.bom'].search([('product_tmpl_id', '=', self.part_b_id.product_tmpl_id.id)], limit=1)

        if not bom_a and not bom_b:
            return [{'message': 'No BOMs found for either part'}]

        if not bom_a:
            return [{'message': 'Part A has no BOM', 'part': self.part_a_name}]

        if not bom_b:
            return [{'message': 'Part B has no BOM', 'part': self.part_b_name}]

        # Create dictionaries of BOM lines
        lines_a = {line.product_id.id: {
            'product': line.product_id.display_name,
            'default_code': line.product_id.default_code or '',
            'quantity': line.product_qty,
            'uom': line.product_uom_id.name
        } for line in bom_a.bom_line_ids}

        lines_b = {line.product_id.id: {
            'product': line.product_id.display_name,
            'default_code': line.product_id.default_code or '',
            'quantity': line.product_qty,
            'uom': line.product_uom_id.name
        } for line in bom_b.bom_line_ids}

        # Find deleted components (in A but not in B)
        for product_id, data in lines_a.items():
            if product_id not in lines_b:
                differences.append({
                    'change_type': 'deleted',
                    'product_name': data['product'],
                    'product_code': data['default_code'],
                    'quantity_a': data['quantity'],
                    'uom': data['uom']
                })

        # Find added components (in B but not in A)
        for product_id, data in lines_b.items():
            if product_id not in lines_a:
                differences.append({
                    'change_type': 'added',
                    'product_name': data['product'],
                    'product_code': data['default_code'],
                    'quantity_b': data['quantity'],
                    'uom': data['uom']
                })

        # Find modified components (in both but with different quantities)
        for product_id in set(lines_a.keys()) & set(lines_b.keys()):
            if lines_a[product_id]['quantity'] != lines_b[product_id]['quantity']:
                differences.append({
                    'change_type': 'modified',
                    'product_name': lines_a[product_id]['product'],
                    'product_code': lines_a[product_id]['default_code'],
                    'quantity_a': lines_a[product_id]['quantity'],
                    'quantity_b': lines_b[product_id]['quantity'],
                    'uom': lines_a[product_id]['uom']
                })

        return differences

    def _compare_documents(self):
        """Compare document control records"""
        differences = []

        if not self.document_a_id and not self.document_b_id:
            return [{'message': 'No documents found for either part'}]

        if not self.document_a_id:
            return [{'message': 'Part A has no document control record'}]

        if not self.document_b_id:
            return [{'message': 'Part B has no document control record'}]

        doc_a = self.document_a_id
        doc_b = self.document_b_id

        # Compare key fields
        fields_to_compare = [
            ('name', 'Format Number'),
            ('customer_part_number', 'Customer Part Number'),
            ('customer_part_description', 'Customer Part Description'),
            ('state', 'Status'),
            ('current_drawing_revision_details', 'Current Revision'),
        ]

        for field_name, label in fields_to_compare:
            val_a = getattr(doc_a, field_name, '')
            val_b = getattr(doc_b, field_name, '')

            if val_a != val_b:
                differences.append({
                    'field': label,
                    'value_a': str(val_a) if val_a else '',
                    'value_b': str(val_b) if val_b else '',
                    'change_type': 'modified'
                })

        # Compare customer
        if doc_a.customer_name != doc_b.customer_name:
            differences.append({
                'field': 'Customer',
                'value_a': doc_a.customer_name.name if doc_a.customer_name else '',
                'value_b': doc_b.customer_name.name if doc_b.customer_name else '',
                'change_type': 'modified'
            })

        # Compare categories
        cats_a = set(doc_a.category_ids.mapped('name'))
        cats_b = set(doc_b.category_ids.mapped('name'))

        if cats_a != cats_b:
            differences.append({
                'field': 'Categories',
                'value_a': ', '.join(cats_a) if cats_a else 'None',
                'value_b': ', '.join(cats_b) if cats_b else 'None',
                'change_type': 'modified'
            })

        return differences

    def _compare_revisions(self):
        """Compare document revisions"""
        differences = []

        if not self.document_a_id and not self.document_b_id:
            return [{'message': 'No documents found for either part'}]

        doc_a = self.document_a_id
        doc_b = self.document_b_id

        revisions_a = doc_a.revision_ids if doc_a else []
        revisions_b = doc_b.revision_ids if doc_b else []

        differences.append({
            'type': 'summary',
            'part_a_revision_count': len(revisions_a),
            'part_b_revision_count': len(revisions_b),
            'part_a_current': doc_a.current_drawing_revision_details if doc_a else 'N/A',
            'part_b_current': doc_b.current_drawing_revision_details if doc_b else 'N/A'
        })

        # Get revision numbers
        rev_nums_a = {rev.revision_number: rev for rev in revisions_a}
        rev_nums_b = {rev.revision_number: rev for rev in revisions_b}

        # Revisions only in A
        for rev_num in set(rev_nums_a.keys()) - set(rev_nums_b.keys()):
            rev = rev_nums_a[rev_num]
            differences.append({
                'change_type': 'only_in_a',
                'revision_number': rev_num,
                'description': rev.revision_description or '',
                'state': rev.state
            })

        # Revisions only in B
        for rev_num in set(rev_nums_b.keys()) - set(rev_nums_a.keys()):
            rev = rev_nums_b[rev_num]
            differences.append({
                'change_type': 'only_in_b',
                'revision_number': rev_num,
                'description': rev.revision_description or '',
                'state': rev.state
            })

        # Common revisions with differences
        for rev_num in set(rev_nums_a.keys()) & set(rev_nums_b.keys()):
            rev_a = rev_nums_a[rev_num]
            rev_b = rev_nums_b[rev_num]

            if rev_a.revision_description != rev_b.revision_description or rev_a.state != rev_b.state:
                differences.append({
                    'change_type': 'different',
                    'revision_number': rev_num,
                    'description_a': rev_a.revision_description or '',
                    'description_b': rev_b.revision_description or '',
                    'state_a': rev_a.state,
                    'state_b': rev_b.state
                })

        return differences

    def _compare_files(self):
        """Compare attachments and files"""
        differences = []

        if not self.document_a_id and not self.document_b_id:
            return [{'message': 'No documents found for either part'}]

        doc_a = self.document_a_id
        doc_b = self.document_b_id

        # Get attachments
        attachments_a = doc_a.drawing_internal_attachment_ids if doc_a else []
        attachments_b = doc_b.drawing_internal_attachment_ids if doc_b else []

        # Create dictionaries by filename
        files_a = {att.name: {
            'name': att.name,
            'size': att.file_size,
            'type': att.mimetype or 'unknown'
        } for att in attachments_a}

        files_b = {att.name: {
            'name': att.name,
            'size': att.file_size,
            'type': att.mimetype or 'unknown'
        } for att in attachments_b}

        # Files only in A
        for filename in set(files_a.keys()) - set(files_b.keys()):
            differences.append({
                'change_type': 'deleted',
                'filename': filename,
                'size': files_a[filename]['size'],
                'type': files_a[filename]['type']
            })

        # Files only in B
        for filename in set(files_b.keys()) - set(files_a.keys()):
            differences.append({
                'change_type': 'added',
                'filename': filename,
                'size': files_b[filename]['size'],
                'type': files_b[filename]['type']
            })

        # Files in both but potentially different
        for filename in set(files_a.keys()) & set(files_b.keys()):
            if files_a[filename]['size'] != files_b[filename]['size']:
                differences.append({
                    'change_type': 'modified',
                    'filename': filename,
                    'size_a': files_a[filename]['size'],
                    'size_b': files_b[filename]['size'],
                    'type': files_a[filename]['type']
                })

        return differences

    def _generate_technical_html(self):
        """Generate HTML for technical information differences"""
        if not self.technical_differences:
            return "<p>No technical information comparison performed</p>"

        try:
            data = json.loads(self.technical_differences)
        except:
            return "<p>Error parsing technical information data</p>"

        if not data:
            return "<p>No technical information to display</p>"

        if data and data[0].get('message'):
            return f"<p>{data[0]['message']}</p>"

        html = '<div class="tech-diff">'
        html += '<table class="table table-bordered table-sm">'
        html += '<thead><tr><th style="width: 30%;">Field</th><th style="width: 35%;">Part A Value</th><th style="width: 35%;">Part B Value</th></tr></thead>'
        html += '<tbody>'

        for item in data:
            change_type = item.get('change_type', '')

            # Apply background color only for modified fields
            if change_type == 'modified':
                html += '<tr style="background-color: #fff3cd;">'
            else:
                html += '<tr>'

            html += f'<td><strong>{item.get("field", "")}</strong></td>'

            val_a = item.get("value_a", "")
            val_b = item.get("value_b", "")

            html += f'<td>{val_a if val_a else "<em style=\'color: #999;\'>Not Set</em>"}</td>'
            html += f'<td>{val_b if val_b else "<em style=\'color: #999;\'>Not Set</em>"}</td>'
            html += '</tr>'

        html += '</tbody></table></div>'
        return html

    def _generate_bom_html(self):
        """Generate HTML for BOM differences"""
        if not self.bom_differences:
            return "<p>No BOM comparison performed</p>"

        try:
            data = json.loads(self.bom_differences)
        except:
            return "<p>Error parsing BOM data</p>"

        if not data:
            return "<p>No BOM differences found</p>"

        if data and data[0].get('message'):
            return f"<p>{data[0]['message']}</p>"

        html = '<div class="bom-diff">'
        html += '<table class="table table-bordered">'
        html += '<thead><tr><th>Type</th><th>Product</th><th>Qty A</th><th>Qty B</th><th>UOM</th></tr></thead>'
        html += '<tbody>'

        for item in data:
            change_type = item.get('change_type')
            if change_type == 'added':
                html += '<tr style="background-color: #d4edda;">'
                html += '<td><span class="badge badge-success">Added</span></td>'
                html += f'<td>{item.get("product_name", "")}</td>'
                # html += f'<td>{item.get("product_code", "")}</td>'
                html += '<td>-</td>'
                html += f'<td>{item.get("quantity_b", 0)}</td>'
                html += f'<td>{item.get("uom", "")}</td>'
                html += '</tr>'
            elif change_type == 'deleted':
                html += '<tr style="background-color: #f8d7da;">'
                html += '<td><span class="badge badge-danger">Deleted</span></td>'
                html += f'<td>{item.get("product_name", "")}</td>'
                # html += f'<td>{item.get("product_code", "")}</td>'
                html += f'<td>{item.get("quantity_a", 0)}</td>'
                html += '<td>-</td>'
                html += f'<td>{item.get("uom", "")}</td>'
                html += '</tr>'
            elif change_type == 'modified':
                html += '<tr style="background-color: #fff3cd;">'
                html += '<td><span class="badge badge-warning">Modified</span></td>'
                html += f'<td>{item.get("product_name", "")}</td>'
                # html += f'<td>{item.get("product_code", "")}</td>'
                html += f'<td>{item.get("quantity_a", 0)}</td>'
                html += f'<td>{item.get("quantity_b", 0)}</td>'
                html += f'<td>{item.get("uom", "")}</td>'
                html += '</tr>'

        html += '</tbody></table></div>'
        return html

    def _generate_document_html(self):
        """Generate HTML for document differences"""
        if not self.document_differences:
            return "<p>No document comparison performed</p>"

        try:
            data = json.loads(self.document_differences)
        except:
            return "<p>Error parsing document data</p>"

        if not data:
            return "<p>No document differences found</p>"

        if data and data[0].get('message'):
            return f"<p>{data[0]['message']}</p>"

        html = '<div class="doc-diff">'
        html += '<table class="table table-bordered">'
        html += '<thead><tr><th>Field</th><th>Part A Value</th><th>Part B Value</th></tr></thead>'
        html += '<tbody>'

        for item in data:
            html += '<tr style="background-color: #fff3cd;">'
            html += f'<td><strong>{item.get("field", "")}</strong></td>'
            html += f'<td>{item.get("value_a", "")}</td>'
            html += f'<td>{item.get("value_b", "")}</td>'
            html += '</tr>'

        html += '</tbody></table></div>'
        return html

    def _generate_revision_html(self):
        """Generate HTML for revision differences"""
        if not self.revision_differences:
            return "<p>No revision comparison performed</p>"

        try:
            data = json.loads(self.revision_differences)
        except:
            return "<p>Error parsing revision data</p>"

        if not data:
            return "<p>No revision differences found</p>"

        html = '<div class="rev-diff">'

        # Summary
        summary = next((item for item in data if item.get('type') == 'summary'), None)
        if summary:
            html += '<div class="alert alert-info">'
            html += f'<p><strong>Part A Revisions:</strong> {summary.get("part_a_revision_count", 0)} (Current: {summary.get("part_a_current", "N/A")})</p>'
            html += f'<p><strong>Part B Revisions:</strong> {summary.get("part_b_revision_count", 0)} (Current: {summary.get("part_b_current", "N/A")})</p>'
            html += '</div>'

        # Detailed differences
        html += '<table class="table table-bordered">'
        html += '<thead><tr><th>Type</th><th>Revision</th><th>Details</th></tr></thead>'
        html += '<tbody>'

        for item in data:
            if item.get('type') == 'summary':
                continue

            change_type = item.get('change_type')
            if change_type == 'only_in_a':
                html += '<tr style="background-color: #f8d7da;">'
                html += '<td><span class="badge badge-danger">Only in A</span></td>'
                html += f'<td>{item.get("revision_number", "")}</td>'
                html += f'<td>{item.get("description", "")} ({item.get("state", "")})</td>'
                html += '</tr>'
            elif change_type == 'only_in_b':
                html += '<tr style="background-color: #d4edda;">'
                html += '<td><span class="badge badge-success">Only in B</span></td>'
                html += f'<td>{item.get("revision_number", "")}</td>'
                html += f'<td>{item.get("description", "")} ({item.get("state", "")})</td>'
                html += '</tr>'
            elif change_type == 'different':
                html += '<tr style="background-color: #fff3cd;">'
                html += '<td><span class="badge badge-warning">Different</span></td>'
                html += f'<td>{item.get("revision_number", "")}</td>'
                html += f'<td>A: {item.get("description_a", "")} ({item.get("state_a", "")})<br>B: {item.get("description_b", "")} ({item.get("state_b", "")})</td>'
                html += '</tr>'

        html += '</tbody></table></div>'
        return html

    def _generate_file_html(self):
        """Generate HTML for file differences"""
        if not self.file_differences:
            return "<p>No file comparison performed</p>"

        try:
            data = json.loads(self.file_differences)
        except:
            return "<p>Error parsing file data</p>"

        if not data:
            return "<p>No file differences found</p>"

        if data and data[0].get('message'):
            return f"<p>{data[0]['message']}</p>"

        html = '<div class="file-diff">'
        html += '<table class="table table-bordered">'
        html += '<thead><tr><th>Type</th><th>Filename</th><th>Size A</th><th>Size B</th><th>Type</th></tr></thead>'
        html += '<tbody>'

        for item in data:
            change_type = item.get('change_type')
            if change_type == 'added':
                html += '<tr style="background-color: #d4edda;">'
                html += '<td><span class="badge badge-success">Added</span></td>'
                html += f'<td>{item.get("filename", "")}</td>'
                html += '<td>-</td>'
                html += f'<td>{item.get("size", 0)} bytes</td>'
                html += f'<td>{item.get("type", "")}</td>'
                html += '</tr>'
            elif change_type == 'deleted':
                html += '<tr style="background-color: #f8d7da;">'
                html += '<td><span class="badge badge-danger">Deleted</span></td>'
                html += f'<td>{item.get("filename", "")}</td>'
                html += f'<td>{item.get("size", 0)} bytes</td>'
                html += '<td>-</td>'
                html += f'<td>{item.get("type", "")}</td>'
                html += '</tr>'
            elif change_type == 'modified':
                html += '<tr style="background-color: #fff3cd;">'
                html += '<td><span class="badge badge-warning">Modified</span></td>'
                html += f'<td>{item.get("filename", "")}</td>'
                html += f'<td>{item.get("size_a", 0)} bytes</td>'
                html += f'<td>{item.get("size_b", 0)} bytes</td>'
                html += f'<td>{item.get("type", "")}</td>'
                html += '</tr>'

        html += '</tbody></table></div>'
        return html