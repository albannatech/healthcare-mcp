"""The installer — what has to exist before this extension is usable.

Two things, both idempotent, because a restored site repairs itself on the
next migrate rather than failing on a missing document the first time somebody
opens the widget.

The role is the load-bearing half.  ``Patient`` and ``Patient Encounter``
grant read/write to ``Healthcare MCP User``, and that row is the gate: an
account may use these tools when it holds that role.  Creating it here rather
than than in a fixture means a site restored from a backup gets it back.

Why the core dependency is checked here and not in ``required_apps``
-------------------------------------------------------------------
Frappe resolves ``required_apps`` through ``installer.parse_app_name``, which
for a bare name does a GitHub lookup under ``frappe/`` and ``erpnext/`` only,
and for an ``org/repo`` form returns the *repository* name.  This portfolio
names its repos ``[APP_NAME]-mcp`` while the package inside is
``[APP_NAME]_mcp``, so neither form resolves to the app name Frappe needs —
declaring it fails with ``InvalidRemoteException``, which reads as a network
fault rather than a naming conflict.

So the check lives here, where it can say what to do.
"""

from __future__ import annotations

import frappe

ROLE = "Healthcare MCP User"
CORE_APP = "albanna_ai_chat"


def after_install() -> None:
    _require_core()
    _ensure_role()
    _ensure_settings()


def after_migrate() -> None:
    """Called on every migrate, so a restored site repairs itself."""
    _require_core()
    _ensure_role()
    _ensure_settings()


def _require_core() -> None:
    """Refuse to install without the core, and say which app to install.

    A raised exception here fails the install, which is correct: an extension
    whose tools cannot be discovered is not an extension, it is a directory.
    """
    if CORE_APP in frappe.get_installed_apps():
        return
    frappe.throw(
        f"Healthcare MCP requires the frappe-mcp core. Install it first: "
        f"bench get-app https://github.com/albannatech/albanna-ai-chat.git "
        f"&& bench --site {{site}} install-app {CORE_APP}",
        title="Missing required app",
    )


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
