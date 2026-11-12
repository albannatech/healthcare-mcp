"""Patient — one person this site holds records for."""

from __future__ import annotations

import frappe
from frappe.model.document import Document


class Patient(Document):
    """One patient.

    The controller is deliberately thin: everything that decides what a tool
    may do lives in the core's authority layer, and everything that decides
    what a turn does lives in the manifest.  A controller that grows business
    rules is a controller that has become a second source of truth.
    """
