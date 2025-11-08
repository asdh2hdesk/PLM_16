from odoo import models
from odoo.exceptions import UserError
import logging
import traceback

_logger = logging.getLogger(__name__)

class BaseModel(models.AbstractModel):
    _inherit = "base"

    @classmethod
    def _call_kw(cls, model, name, args, kwargs):
        """
        Global exception handler:
        - Catch all unexpected errors
        - Raise a clean UserError message (no Odoo branding)
        - Log full traceback in server logs
        """
        try:
            return super(BaseModel, cls)._call_kw(model, name, args, kwargs)

        except UserError:
            # Already a user-facing message → re-raise without changes
            raise

        except Exception as e:
            # Log full traceback for developers
            tb = traceback.format_exc()
            _logger.error("⚠️ Global Exception in %s.%s\n%s", model, name, tb)

            # Raise a clean, user-friendly error message
            raise UserError("⚠️ An unexpected error occurred. Please contact support.")

