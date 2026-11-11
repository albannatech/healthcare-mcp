"""What this extension contributes to the core — the whole contract.

An extension is a Frappe app that implements the ``frappe_mcp_tools`` hook.
This module is what that hook points at: ``TOOLS`` (a list of ``ToolSpec``)
and ``TIERS`` (every name classified).  The core validates both atomically
and absorbs them tagged with this app's name, so uninstalling removes exactly
these tools and nothing else.

Why the surface looks like this
-------------------------------
Nine tools, and one of them is a flow.  The ratio is deliberate and it is the
ratio ``erpnext-mcp`` ships: 451 tools, eleven flows.  A rule that turns every
tool into a flow is not that ratio — it makes every write a transaction that
can half-fail, and every one of them then owes a compensation entry.

``admit_patient`` is the flow, and it is a genuine multi-step transaction:
create the patient, create the encounter that patient is admitted for, assign
the practitioner who will see them.  Three documents, one intent, and a
half-finished admission is a patient with an encounter and nobody assigned.

Every write declares how it is undone
-------------------------------------
``create_patient`` is undone by ``delete_patient``.  ``create_encounter`` is
undone by ``cancel_encounter``.  ``assign_practitioner`` is undone by
``unassign_practitioner``.  The two deletions and the cancellation are
irreversible, so they say so with a reason rather than hiding behind prose —
which is what ``mechanism="none"`` means, and why the validator demands the
reason.

Nothing here imports Frappe
---------------------------
The manifest is the contract, and the contract must be importable on a machine
with none of this app's dependencies installed — that is what lets the core
validate it before anything runs.  The handlers live in ``patient.py``.
"""

from __future__ import annotations

from albanna_ai_chat.core.flow import CompensationSpec, FlowSpec, FlowStep
from albanna_ai_chat.core.tools import READ, WRITE, ToolSpec

#: The DocTypes this extension owns.  One module, and the doctypes its domain
#: actually has — not one doctype per tool.
PATIENT = "Patient"
ENCOUNTER = "Patient Encounter"


def _schema(properties: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

LIST_PATIENTS = ToolSpec(
    name="list_patients",
    description=(
        "Find patients on this site. Use this to answer 'who is admitted', "
        "'which patients were seen last week', 'who is waiting for a "
        "practitioner'. Returns a compact list of matching patients. Fetch "
        "the DocType schema with get_doctype_meta first if you are not "
        "certain which fields exist."
    ),
    parameters=_schema(
        {
            "filters": {
                "type": "array",
                "description": (
                    "Filter conditions, each one exactly three strings: "
                    "[fieldname, operator, value]. Operators: =, !=, >, <, "
                    ">=, <=, like, not like, in, not in, is, between. Omit "
                    "to list everything."
                ),
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 3,
                    "maxItems": 3,
                },
            },
            "fields": {
                "type": "array",
                "description": "Fieldnames to return. Omit for the name and title field.",
                "items": {"type": "string"},
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "description": "How many patients to return (default 20).",
            },
        },
        [],
    ),
    tier=READ,
    doctype_arg="",
)

GET_PATIENT = ToolSpec(
    name="get_patient",
    description=(
        "Fetch one patient by name. Use this to read the detail behind a "
        "name you got from list_patients. Name the fields you need to keep "
        "the answer short."
    ),
    parameters=_schema(
        {
            "name": {"type": "string", "description": "The patient's name, e.g. 'PAT-0001'."},
            "fields": {
                "type": "array",
                "description": "Fieldnames to return. Omit for the whole document.",
                "items": {"type": "string"},
            },
        },
        ["name"],
    ),
    tier=READ,
)


# --------------------------------------------------------------------------
# Single-step writes, each with its own compensation
# --------------------------------------------------------------------------

CREATE_PATIENT = ToolSpec(
    name="create_patient",
    description=(
        "Create a patient record. Use this only when the user has asked for "
        "a patient to be created — never to test that something works, and "
        "never on a guess. If a required field is missing, ask the user for "
        "it rather than inventing a value."
    ),
    parameters=_schema(
        {
            "patient_name": {"type": "string", "description": "The patient's full name."},
            "sex": {
                "type": "string",
                "description": "The patient's sex, as the site records it.",
            },
            "dob": {
                "type": "string",
                "description": "Date of birth, as YYYY-MM-DD.",
            },
            "blood_group": {
                "type": "string",
                "description": "Blood group, e.g. 'O Positive'. Omit when unknown.",
            },
            "phone": {"type": "string", "description": "Contact number. Omit when unknown."},
        },
        ["patient_name"],
    ),
    tier=WRITE,
    doctype_arg="",
    write_permission="create",
    # Creating a patient is undone by deleting them, and delete_patient is a
    # real tool in this extension — so this is a genuine inverse, not a claim.
    compensation=CompensationSpec(mechanism="reverse", undo_with=("delete_patient",)),
)

DELETE_PATIENT = ToolSpec(
    name="delete_patient",
    description=(
        "Delete a patient record. Use this only when the user has explicitly "
        "asked for the patient to be deleted. Deletion cannot be undone from "
        "here — say so rather than trying."
    ),
    parameters=_schema(
        {"name": {"type": "string", "description": "The patient's name."}},
        ["name"],
    ),
    tier=WRITE,
    write_permission="delete",
    # Irreversible, and it says why rather than pretending an undo exists.
    compensation=CompensationSpec(
        mechanism="none",
        reason=(
            "A deleted patient record is not recoverable from here. The "
            "operator holds a site backup; this tool does not."
        ),
    ),
)

CREATE_ENCOUNTER = ToolSpec(
    name="create_encounter",
    description=(
        "Create a patient encounter — a visit, an admission, a consultation. "
        "Use this when the user asks for a patient to be seen or admitted. "
        "Give the patient it belongs to."
    ),
    parameters=_schema(
        {
            "patient": {"type": "string", "description": "The patient's name."},
            "encounter_type": {
                "type": "string",
                "description": "What kind of encounter, e.g. 'Admission', 'Consultation'.",
            },
            "practitioner": {
                "type": "string",
                "description": "The practitioner who will see the patient. Omit to assign later.",
            },
        },
        ["patient"],
    ),
    tier=WRITE,
    doctype_arg="",
    write_permission="create",
    compensation=CompensationSpec(mechanism="reverse", undo_with=("cancel_encounter",)),
)

CANCEL_ENCOUNTER = ToolSpec(
    name="cancel_encounter",
    description=(
        "Cancel a patient encounter. Use this when the user names an "
        "encounter and asks for it to be cancelled. Only an open encounter "
        "can be cancelled."
    ),
    parameters=_schema(
        {"name": {"type": "string", "description": "The encounter's name."}},
        ["name"],
    ),
    tier=WRITE,
    write_permission="cancel",
    compensation=CompensationSpec(
        mechanism="none",
        reason=(
            "A cancelled encounter keeps its history and cannot be reopened; "
            "a new encounter is created instead."
        ),
    ),
)

ASSIGN_PRACTITIONER = ToolSpec(
    name="assign_practitioner",
    description=(
        "Assign a practitioner to an encounter. Use this when the user names "
        "an encounter and asks who will see the patient."
    ),
    parameters=_schema(
        {
            "encounter": {"type": "string", "description": "The encounter's name."},
            "practitioner": {"type": "string", "description": "The practitioner's name."},
        },
        ["encounter", "practitioner"],
    ),
    tier=WRITE,
    doctype_arg="",
    write_permission="write",
    # The inverse of assigning somebody is assigning nobody, and
    # unassign_practitioner is the tool that does it.
    compensation=CompensationSpec(
        mechanism="reverse", undo_with=("unassign_practitioner",)
    ),
)

UNASSIGN_PRACTITIONER = ToolSpec(
    name="unassign_practitioner",
    description=(
        "Remove the practitioner from an encounter, leaving it unassigned. "
        "Use this when the user asks for an assignment to be taken back."
    ),
    parameters=_schema(
        {"encounter": {"type": "string", "description": "The encounter's name."}},
        ["encounter"],
    ),
    tier=WRITE,
    doctype_arg="",
    write_permission="write",
    compensation=CompensationSpec(
        mechanism="none",
        reason=(
            "Clearing an assignment loses who was assigned; the encounter's "
            "own history is the only record."
        ),
    ),
)


# --------------------------------------------------------------------------
# The flow
# --------------------------------------------------------------------------

ADMIT_PATIENT = ToolSpec(
    name="admit_patient",
    description=(
        "Admit a patient: create the patient, open an encounter for the "
        "admission, and assign the practitioner who will see them — as one "
        "step. Use this when the user asks for a patient to be admitted, "
        "rather than calling the three tools separately. If any step fails "
        "the ones before it are undone, so a half-finished admission is "
        "never left behind."
    ),
    parameters=_schema(
        {
            "patient_name": {"type": "string", "description": "The patient's full name."},
            "sex": {"type": "string", "description": "The patient's sex."},
            "dob": {"type": "string", "description": "Date of birth, as YYYY-MM-DD."},
            "encounter_type": {
                "type": "string",
                "description": "What kind of encounter, e.g. 'Admission'.",
            },
            "practitioner": {
                "type": "string",
                "description": "The practitioner who will see the patient.",
            },
        },
        ["patient_name", "practitioner"],
    ),
    tier=WRITE,
    doctype_arg="",
    write_permission="create",
    # A flow carries its own compensation: several calls, several things to
    # undo. Declaring compensation on the spec as well would be two answers
    # to one question, which the validator refuses.
    flow=FlowSpec(
        name="admit_patient",
        description=(
            "Create the patient, open their encounter, and assign the "
            "practitioner — one transaction."
        ),
        steps=(
            FlowStep(
                tool="create_patient",
                arguments={
                    "patient_name": "{patient_name}",
                    "sex": "{sex}",
                    "dob": "{dob}",
                },
            ),
            FlowStep(
                tool="create_encounter",
                # The encounter belongs to the patient step 0 just made, so
                # it consumes that step's output rather than guessing a name.
                from_step=0,
                from_field="name",
                arguments={
                    "patient": "{patient_name}",
                    "encounter_type": "{encounter_type}",
                },
            ),
            FlowStep(
                tool="assign_practitioner",
                from_step=1,
                from_field="name",
                arguments={"practitioner": "{practitioner}"},
            ),
        ),
        # Undone in reverse: cancel the encounter, then delete the patient.
        # The practitioner assignment needs no undo of its own — cancelling
        # the encounter it belongs to removes it.
        compensation=CompensationSpec(
            mechanism="reverse",
            undo_with=("cancel_encounter", "delete_patient"),
        ),
    ),
)


#: Every tool this extension contributes.
TOOLS = [
    LIST_PATIENTS,
    GET_PATIENT,
    CREATE_PATIENT,
    DELETE_PATIENT,
    CREATE_ENCOUNTER,
    CANCEL_ENCOUNTER,
    ASSIGN_PRACTITIONER,
    UNASSIGN_PRACTITIONER,
    ADMIT_PATIENT,
]

#: Every tool classified.  The validator refuses a tool that is not here, so
#: this dict and TOOLS are kept in step by a test rather than by memory.
TIERS = {
    "list_patients": READ,
    "get_patient": READ,
    "create_patient": WRITE,
    "delete_patient": WRITE,
    "create_encounter": WRITE,
    "cancel_encounter": WRITE,
    "assign_practitioner": WRITE,
    "unassign_practitioner": WRITE,
    "admit_patient": WRITE,
}

#: The core version range this extension is built against.
#:
#: Read by the core as ``REQUIRES_CORE`` and checked against *activation*, not
#: installation: an extension whose range excludes the running core is
#: reported as incompatible and refused activation — a visible Settings row
#: rather than a runtime surprise.
#:
#: The range is ``>=0.1.0,<0.2.0`` because the core is pre-1.0 and its
#: contract is not yet frozen.  A pre-1.0 core may change any part of the
#: contract in a minor release, so pinning to the minor is the honest
#: declaration; widening it to ``<1.0.0`` would promise a stability the core
#: has not earned.  When the core reaches 1.0.0 this becomes ``>=1.0.0,<2.0.0``
#: and the widening is a real event, not a guess.
REQUIRES_CORE = ">=0.1.0,<0.2.0"
