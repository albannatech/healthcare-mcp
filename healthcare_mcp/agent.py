"""The agent this extension brings, and the prompts it brings with it.

An extension is not only tools.  The user's architecture has every repo
carrying its own tools, permissions, configurations, *agent* and *prompts* —
and the agent is what makes a set of tools into something with a point of
view.  A chat with nine healthcare tools and no agent is a chat that will
happily admit a patient to answer a question about opening hours.

This module is pure data.  It is Frappe-free so it can be tested without a
site, and so the core can assemble a system prompt from it without importing
anything this extension depends on.

How the core uses it
--------------------
The core's prompt assembler is deterministic and ordered: the core's own
system prompt, then the *active* extension's agent persona, then its task
prompts, then the conversation.  One active agent per conversation, chosen in
Settings and switchable mid-thread with the switch recorded.  Twenty
extensions contribute *content*; none of them contributes assembly logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: This extension's name, as the core knows it.  It is the app name, because
#: that is what provenance is tagged with and what an uninstall keys on.
EXTENSION_NAME = "healthcare_mcp"


@dataclass(frozen=True)
class Prompt:
    """One instruction the agent is given.

    ``when`` says when it applies, so the assembler can include the prompts
    that matter for this turn rather than all of them every time — a prompt
    nobody needs is a prompt that dilutes the ones that do.
    """

    name: str
    text: str
    #: When this prompt applies.  ``"always"``, or the name of a tool or a
    #: situation it belongs to.
    when: str = "always"


@dataclass(frozen=True)
class Agent:
    """The persona and the rules this extension's agent brings."""

    name: str
    #: One sentence, in the reader's language, saying what this agent is for.
    purpose: str
    #: The persona.  Written for a model, not a developer: it says what this
    #: agent is careful about, in terms a model can act on.
    persona: str
    #: What this agent will not do.  A refusal the model can act on is worth
    #: more than a permission it cannot.
    boundaries: tuple[str, ...] = ()
    prompts: tuple[Prompt, ...] = field(default_factory=tuple)

    def prompts_for(self, when: str) -> list[Prompt]:
        """The prompts that apply now: the always-on ones plus this one."""
        return [p for p in self.prompts if p.when in ("always", when)]


HEALTHCARE_AGENT = Agent(
    name="Healthcare Assistant",
    purpose=(
        "Answer questions about this site's patients and encounters, and act "
        "on them when the reader asks."
    ),
    persona=(
        "You are careful with patient records, because a wrong entry in one "
        "is a wrong entry in somebody's medical history. Read before you "
        "write: fetch the patient with get_patient before changing anything "
        "about them, so you are working from what the site actually holds "
        "rather than what you assume it holds. When a required field is "
        "missing, ask the reader for it rather than inventing a value — a "
        "guessed date of birth is a wrong date of birth. Say what you did in "
        "the reader's own terms, and name the record you touched so they can "
        "check it."
    ),
    boundaries=(
        "Never create, change or delete a patient record the reader did not name.",
        "Never guess a date of birth, a blood group or a contact number — ask.",
        "Never admit a patient to answer a question that is not about admission.",
        "Never report a write as done when it was refused; a refusal is the "
        "reader lacking a right, and the answer is to say so.",
    ),
    prompts=(
        Prompt(
            name="read_before_write",
            text=(
                "Before changing a patient or an encounter, read it first. "
                "You are working from what the site holds, not from what you "
                "remember being told."
            ),
            when="always",
        ),
        Prompt(
            name="admission_is_one_step",
            text=(
                "Admitting a patient is one call to admit_patient, not three. "
                "It creates the patient, opens the encounter and assigns the "
                "practitioner together, and undoes the earlier steps if a "
                "later one fails. Do not call create_patient, create_encounter "
                "and assign_practitioner separately unless the reader asked "
                "for exactly that."
            ),
            when="admit_patient",
        ),
        Prompt(
            name="deletion_is_explicit",
            text=(
                "delete_patient cannot be undone from here. Use it only when "
                "the reader has explicitly asked for the patient to be "
                "deleted, and say that it cannot be undone."
            ),
            when="delete_patient",
        ),
        Prompt(
            name="name_what_you_touched",
            text=(
                "After a write, name the record you changed — its name, not "
                "only its description — so the reader can open it and check."
            ),
            when="always",
        ),
    ),
)


def system_prompt(agent: Agent = HEALTHCARE_AGENT) -> str:
    """The agent's contribution to the system prompt.

    Ordered and deterministic: purpose, persona, boundaries, then the
    always-on prompts.  The core prepends its own prompt and appends the
    conversation, so the same inputs always produce the same string — which
    is what makes it testable.
    """
    parts = [
        f"# {agent.name}",
        "",
        agent.purpose,
        "",
        agent.persona,
        "",
        "## What you will not do",
        "",
    ]
    parts.extend(f"- {line}" for line in agent.boundaries)
    parts.append("")
    parts.append("## Always")
    parts.append("")
    for prompt in agent.prompts_for("always"):
        parts.append(f"### {prompt.name}")
        parts.append("")
        parts.append(prompt.text)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"
