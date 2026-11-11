"""The installer — what has to exist before this extension is usable.

Two things, both idempotent, because a restored site repairs itself on the
next migrate rather than failing on a missing document the first time somebody
opens the widget.

The role is the load-bearing half.  ``Patient`` and ``Patient Encounter``
grant read/write to ``Healthcare MCP User``, and that row is the gate: an
account may use these tools when it holds that role.  Creating it here rather
than than in a fixture means a site restored from a backup gets it back.
"""

from __future__ import annotations

import frappe

ROLE = "Healthcare MCP User"


def after_install() -> None:
    _ensure_role()
    _ensure_settings()


def after_migrate() -> None:
    """Called on every migrate, so a restored site repairs itself."""
    _ensure_role()
    _ensure_settings()


def _ensure_role() -> None:
    if frappe.db.exists("Role", ROLE):
        return
    frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert(
        ignore_permissions=True
    )


def _ensure_settings() -> None:
    """The Single settings row, so the extension is configurable immediately."""
    if frappe.db.exists("Healthcare MCP Settings", "Healthcare MCP Settings"):
        return
    frappe.get_doc(
        {
            "doctype": "Healthcare MCP Settings",
            "default_encounter_type": "Admission",
            "require_practitioner_on_admission": 1,
        }
    ).insert(ignore_permissions=True)
