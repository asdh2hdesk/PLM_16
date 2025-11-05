# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from .selection import ApproverState, ApprovalMethods, ApprovalStep

class DocProjectTypes(models.Model):
    _name = 'doc.project.type'


    name = fields.Char('Project Type')


class DocFOrmate(models.Model):
    _name = 'document.formate'
    _order = 'sr_no asc'
    _inherit = "translation.mixin"

    serial_no = fields.Integer(string='Serial NO.')
    sr_no = fields.Integer(string='Sequence No.')
    control_emp_ids = fields.Many2many('hr.employee', 'emp_idx', string='Control Employee')
    control_department_ids = fields.Many2many('hr.department', 'dep_idsx', string='Control Departments', compute='_compute_approval_departments')
    # control_department_ids = fields.Many2many('hr.department', 'dep_idsx', string='control Departments')
    name = fields.Char('Name',translate=True)
    table = fields.Char('Table',translate=True)
    department_ids = fields.Many2many('hr.department', 'asd', string='Departments')
    used_in_project_type_ids = fields.Many2many(string='Used in Project type', required=True, comodel_name='doc.project.type')

    @api.depends('control_emp_ids')
    def _compute_approval_departments(self):
        for rec in self:
            # formate_id = self.env[rec.formate.table].sudo().search([('id', '=', rec.formate_id)])
            department_ids = rec.control_emp_ids.mapped('department_id')
            rec.control_department_ids = [(6, 0, department_ids.ids)]
