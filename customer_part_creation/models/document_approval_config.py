# -*- coding: utf-8 -*-

from odoo import models, fields, api

class DocumentApprovalConfig(models.Model):
    _name = 'document.approval.config'
    _description = 'Document Approval Configuration'

    approver_ids = fields.Many2many('res.users', string='Approvers')