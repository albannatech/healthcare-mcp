"""Patient Encounter — one visit, admission or consultation."""

from __future__ import annotations

import frappe
from frappe.model.document import Document


class PatientEncounter(Document):
    """One encounter.

    ``practitioner`` is the field ``assign_practitioner`` writes and
    ``unassign_practitioner`` clears, so the two are kept in step by the
    manifest rather than by a rule here.
    """
