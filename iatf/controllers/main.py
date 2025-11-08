# controllers/main.py
import base64
from odoo import http, fields
from odoo.http import request
from werkzeug.exceptions import Forbidden


class QrController(http.Controller):

    @http.route('/qr/<int:qr_id>', type='http', auth='user', website=True)
    def qr_detail(self, qr_id, **kw):
        """ Display equipment details and documents when QR is scanned """
        qr = request.env['qr.qr'].sudo().browse(qr_id)
        if not qr.exists():
            return request.render('web.404')

        # Check if user is admin
        is_admin = request.env.user.has_group('base.group_system')

        return request.render('qr.equipment_document_portal', {
            'qr_id': qr,
            'is_admin': is_admin,
        })

    @http.route('/qr/upload_document', type='http', auth='user', methods=['POST'], csrf=False)
    def upload_document(self, **post):
        """ Handle document upload for admin users """
        # Security check
        if not request.env.user.has_group('base.group_system'):
            return {'success': False, 'error': 'Permission denied'}

        try:
            equipment_id = int(post.get('equipment_id'))
            qr_id = int(post.get('qr_id'))
            document_type = post.get('document_type')
            doc_name = post.get('doc_name')
            revision_no = post.get('revision_no')
            revision_date = post.get('revision_date') or False
            pdf_file = post.get('pdf_file')

            # File processing
            if hasattr(pdf_file, 'read'):
                file_content = base64.b64encode(pdf_file.read())
                file_name = pdf_file.filename
            else:
                return {'success': False, 'error': 'Invalid file'}

            # Create attachment
            attachment = request.env['qr.attachments'].sudo().create({
                'name': doc_name,
                'item': equipment_id,
                'qr_id': qr_id,
                'document_type': document_type,
                'revision_no': revision_no,
                'revision_date': revision_date,
                'pdf_file': file_content,
                'pdf_filename': file_name,
            })

            return {'success': True, 'attachment_id': attachment.id}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/qr/delete_document', type='json', auth='user')
    def delete_document(self, document_id):
        """ Handle document deletion for admin users """
        # Security check
        if not request.env.user.has_group('base.group_system'):
            return {'success': False, 'error': 'Permission denied'}

        try:
            document = request.env['qr.attachments'].sudo().browse(int(document_id))
            if document.exists():
                document.unlink()
                return {'success': True}
            else:
                return {'success': False, 'error': 'Document not found'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/web/content/<string:model>/<int:id>', type='http', auth='user')
    def download_document(self, model, id, **kw):
        """ Download the document """
        if model != 'qr.attachments':
            return request.not_found()

        attachment = request.env[model].sudo().browse(id)
        if not attachment.exists():
            return request.not_found()

        # Create response with proper headers
        return http.request.make_response(
            base64.b64decode(attachment.pdf_file),
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="{attachment.pdf_filename}"')
            ]
        )