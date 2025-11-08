
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import difflib
from datetime import datetime

class ProductTechnicalAttribute(models.Model):
    _name = 'product.technical.attribute'
    _description = 'Product Technical Attributes'

    product_id = fields.Many2one('product.product', string='Product', required=True, ondelete='cascade')
    attribute_name = fields.Char(string='Attribute Name', required=True)
    attribute_value = fields.Char(string='Value', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    readonly_state = fields.Boolean(compute='_compute_readonly_state')

    @api.depends('product_id.engineering_state')
    def _compute_readonly_state(self):
        for rec in self:
            rec.readonly_state = rec.product_id.engineering_state in ['released', 'obsoleted']


class ProductProduct(models.Model):
    _inherit = 'product.product'

    technical_attribute_ids = fields.One2many(
        'product.technical.attribute',
        'product_id',
        string='Technical Attributes'
    )