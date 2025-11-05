from odoo import models, fields, api


class XfDocApprovalDocumentPackage(models.Model):
    _inherit = 'xf.doc.approval.document.package'

    @api.model
    def get_project_type_state_distribution(self):
        """
        Dynamically generate project type distribution across different states
        """
        states = ['draft', 'approval', 'approved']
        distribution = {}

        for state in states:
            state_distribution = self.read_group(
                [('state', '=', state)],
                ['used_in_project_type_id', 'id:count'],
                ['used_in_project_type_id']
            )
            distribution[state] = state_distribution

        return distribution

    def action_generate_project_type_pie_chart(self):
        """
        Generate pie chart data for project types and states
        """
        distribution = self.get_project_type_state_distribution()

        # You can further process or visualize the distribution here
        # This could be used to generate a dynamic chart or report
        return distribution