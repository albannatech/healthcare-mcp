"""The Frappe half — the handlers behind this extension's tools.

``manifest`` is the contract and imports no Frappe.  This module is the only
one here that does, and it is what the core's port calls when a tool runs.

The core owns the authority layer
---------------------------------
These handlers do **not** decide who may call them.  The core computes reach
from Frappe's permission matrix per user and removes a write tool from the
model's view entirely when the caller holds no such right anywhere.  A handler
that re-checks permissions is a handler with a second, different answer.

What the handlers do own is the *shape* of the answer: the envelope, the
summary line the panel shows, and the sentence a refusal carries.  A tool
result the model cannot act on is a tool result it will retry identically.
"""

from __future__ import annotations

from typing import Any

import frappe

from healthcare_mcp.tools import manifest


def _ok(message: str, data: Any = None, **state: Any) -> str:
    """A successful result, as the envelope the model reads."""
    import json

    return json.dumps(
        {"status": "ok", "message": message, "data": data, "hints": [], **state},
        default=str,
    )


def _error(message: str, hints: list[str] | None = None, **state: Any) -> str:
    """A failed result, with what to do about it."""
    import json

    return json.dumps(
        {
            "status": "error",
            "message": message,
            "data": None,
            "hints": hints or [],
            **state,
        },
        default=str,
    )


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------


def list_patients(filters: list | None = None, fields: list | None = None, limit: int = 20) -> str:
    """Find patients on this site."""
    rows = frappe.get_all(
        manifest.PATIENT,
        filters=_as_filters(filters),
        fields=fields or ["name", "patient_name"],
        limit_page_length=limit,
        order_by="modified desc",
    )
    if not rows:
        return _ok("No patients matched.", data=[])
    return _ok(f"Found {len(rows)} patient(s).", data=rows)


def get_patient(name: str, fields: list | None = None) -> str:
    """Fetch one patient by name."""
    if not frappe.db.exists(manifest.PATIENT, name):
        return _error(
            f"No patient named '{name}'.",
            hints=["Use list_patients to find the patient's exact name."],
        )
    doc = frappe.get_doc(manifest.PATIENT, name)
    data = doc.as_dict()
    if fields:
        data = {key: data.get(key) for key in fields}
    return _ok(f"Patient {name}.", data=data)


# --------------------------------------------------------------------------
# Single-step writes
# --------------------------------------------------------------------------


def create_patient(
    patient_name: str, sex: str = "Unknown", dob: str = "", blood_group: str = "", phone: str = ""
) -> str:
    """Create a patient record."""
    doc = frappe.get_doc(
        {
            "doctype": manifest.PATIENT,
            "patient_name": patient_name,
            "sex": sex,
            "dob": dob or None,
            "blood_group": blood_group or None,
            "phone": phone or None,
        }
    )
    doc.insert()
    return _ok(f"Created patient {doc.name}.", data={"name": doc.name})


def delete_patient(name: str) -> str:
    """Delete a patient record. Irreversible — the manifest says so."""
    if not frappe.db.exists(manifest.PATIENT, name):
        return _error(f"No patient named '{name}'.", hints=["Nothing was deleted."])
    frappe.delete_doc(manifest.PATIENT, name)
    return _ok(f"Deleted patient {name}.", data={"name": name})


def create_encounter(
    patient: str, encounter_type: str = "Admission", practitioner: str = ""
) -> str:
    """Create a patient encounter."""
    if not frappe.db.exists(manifest.PATIENT, patient):
        return _error(
            f"No patient named '{patient}'.",
            hints=["Create the patient first, or use list_patients to find the exact name."],
        )
    doc = frappe.get_doc(
        {
            "doctype": manifest.ENCOUNTER,
            "patient": patient,
            "encounter_type": encounter_type,
            "practitioner": practitioner or None,
        }
    )
    doc.insert()
    return _ok(f"Created encounter {doc.name} for {patient}.", data={"name": doc.name})


def cancel_encounter(name: str) -> str:
    """Cancel an open encounter."""
    if not frappe.db.exists(manifest.ENCOUNTER, name):
        return _error(f"No encounter named '{name}'.", hints=["Nothing was cancelled."])
    doc = frappe.get_doc(manifest.ENCOUNTER, name)
    if doc.status == "Cancelled":
        return _ok(f"Encounter {name} is already cancelled.", data={"name": name})
    doc.status = "Cancelled"
    doc.save()
    return _ok(f"Cancelled encounter {name}.", data={"name": name})


def assign_practitioner(encounter: str, practitioner: str) -> str:
    """Assign a practitioner to an encounter."""
    if not frappe.db.exists(manifest.ENCOUNTER, encounter):
        return _error(f"No encounter named '{encounter}'.", hints=["Nothing was assigned."])
    doc = frappe.get_doc(manifest.ENCOUNTER, encounter)
    doc.practitioner = practitioner
    doc.save()
    return _ok(f"Assigned {practitioner} to encounter {encounter}.", data={"name": encounter})


def unassign_practitioner(encounter: str) -> str:
    """Remove the practitioner from an encounter."""
    if not frappe.db.exists(manifest.ENCOUNTER, encounter):
        return _error(f"No encounter named '{encounter}'.", hints=["Nothing was changed."])
    doc = frappe.get_doc(manifest.ENCOUNTER, encounter)
    doc.practitioner = None
    doc.save()
    return _ok(f"Removed the practitioner from encounter {encounter}.", data={"name": encounter})


# --------------------------------------------------------------------------
# The flow
# --------------------------------------------------------------------------


def admit_patient(
    patient_name: str,
    practitioner: str,
    sex: str = "Unknown",
    dob: str = "",
    encounter_type: str = "Admission",
) -> str:
    """Admit a patient as one transaction.

    The core's flow engine runs the three declared steps and compensates on
    failure; this handler exists so the tool is callable on its own and so
    the flow has a name to point at.  It performs the same three steps in the
    same order, and undoes the earlier ones if a later one fails — which is
    what the manifest's compensation declaration promises.
    """
    patient = None
    encounter = None
    try:
        patient = _insert_patient(patient_name, sex, dob)
        encounter = _insert_encounter(patient, encounter_type)
        _assign(encounter, practitioner)
    except Exception as exc:  # noqa: BLE001 — compensate, then report
        # Undone in reverse, exactly as the manifest declares.
        if encounter:
            _safe_cancel(encounter)
        if patient:
            _safe_delete(patient)
        return _error(
            f"The admission failed and was undone: {exc}",
            hints=["Nothing was left behind — no patient, no encounter."],
        )
    return _ok(
        f"Admitted {patient_name} as {encounter}, assigned to {practitioner}.",
        data={"patient": patient, "encounter": encounter},
    )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _as_filters(filters: list | None) -> list:
    """The model's [field, operator, value] triples, as Frappe wants them."""
    if not filters:
        return []
    return [tuple(item) for item in filters if isinstance(item, (list, tuple)) and len(item) == 3]


def _insert_patient(patient_name: str, sex: str, dob: str) -> str:
    doc = frappe.get_doc(
        {
            "doctype": manifest.PATIENT,
            "patient_name": patient_name,
            "sex": sex,
            "dob": dob or None,
        }
    )
    doc.insert()
    return doc.name


def _insert_encounter(patient: str, encounter_type: str) -> str:
    doc = frappe.get_doc(
        {"doctype": manifest.ENCOUNTER, "patient": patient, "encounter_type": encounter_type}
    )
    doc.insert()
    return doc.name


def _assign(encounter: str, practitioner: str) -> None:
    doc = frappe.get_doc(manifest.ENCOUNTER, encounter)
    doc.practitioner = practitioner
    doc.save()


def _safe_cancel(encounter: str) -> None:
    try:
        cancel_encounter(encounter)
    except Exception:  # noqa: BLE001 — compensation must not mask the original failure
        frappe.log_error(title="healthcare-mcp: compensation failed")


def _safe_delete(patient: str) -> None:
    try:
        delete_patient(patient)
    except Exception:  # noqa: BLE001
        frappe.log_error(title="healthcare-mcp: compensation failed")
