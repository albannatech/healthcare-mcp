# Healthcare MCP

**A reference extension for the [`frappe-mcp` core](https://github.com/albannatech/albanna-ai-chat).**

> **Status: contract complete and tested against the real core.**
> The manifest, the flow, the compensation declarations, the agent and the
> prompts are all validated by the core's own validator — 29 tests, plain
> `pytest`, no bench. The Frappe handlers and doctypes are written but have
> not been installed on a site yet.

---

## What this is

This is the worked example every other `-mcp` repo is generated from. It proves
the whole extension contract end to end:

| The extension brings | Where it lives |
|---|---|
| **Tools** | `healthcare_mcp/tools/manifest.py` — 9 tools, 1 flow |
| **Permissions** | declared on each spec; **enforced by the core**, not here |
| **Configurations** | `Healthcare MCP Settings` (Single) |
| **Agent** | `healthcare_mcp/agent.py` — persona, boundaries, 4 prompts |
| **Prompts** | same module, selected by the core's assembler |

It is deliberately small. Nine tools, one flow, two doctypes. A reference that
is not small is a reference nobody reads.

## Installing it

```bash
bench get-app https://github.com/albannatech/healthcare-mcp.git
bench --site <site> install-app healthcare_mcp
```

Then **activate** it in the core's Settings surface. Installation and
activation are two different things: the first is bench work, the second is a
settings change. The Settings surface reports which one you have done.

## The one line that wires it in

```python
# healthcare_mcp/hooks.py
frappe_mcp_tools = "healthcare_mcp.tools.manifest"
```

The core resolves that hook **per site**, validates it atomically, and absorbs
the tools tagged with this app's name. Install this app and the chat gains a
healthcare agent that knows about patients; uninstall it and those tools are
gone, and only those tools.

**Why a Frappe hook and not a Python entry point:** an entry point lives in the
bench *virtualenv*, which every site on the bench shares. Install this
extension there and its tools appear on every site running the core — including
sites that do not have this app installed, where `Patient` and
`Patient Encounter` do not exist. A Frappe hook is site-scoped, and the scoping
comes for free.

## The tools

| Tool | Tier | Compensation |
|---|---|---|
| `list_patients` | read | — |
| `get_patient` | read | — |
| `create_patient` | write | `reverse` → `delete_patient` |
| `delete_patient` | write | `none` — *a deleted record is not recoverable from here* |
| `create_encounter` | write | `reverse` → `cancel_encounter` |
| `cancel_encounter` | write | `none` — *a cancelled encounter cannot be reopened* |
| `assign_practitioner` | write | `reverse` → `unassign_practitioner` |
| `unassign_practitioner` | write | `none` — *clearing an assignment loses who was assigned* |
| `admit_patient` | write | **flow** — `reverse` → `cancel_encounter`, `delete_patient` |

### The ratio is deliberate

Nine tools, one flow. `erpnext-mcp` ships 451 tools and eleven flows. A rule
that turns every tool into a flow is not that ratio — it makes every write a
transaction that can half-fail, and every one of them then owes a compensation
entry.

`admit_patient` is the flow, and it is a genuine multi-step transaction: create
the patient, open the encounter they are admitted for, assign the practitioner
who will see them. Three documents, one intent — and a half-finished admission
is a patient with an encounter and nobody assigned.

```python
FlowSpec(
    name="admit_patient",
    steps=(
        FlowStep(tool="create_patient", arguments={...}),
        # The encounter belongs to the patient step 0 just made, so it
        # consumes that step's output rather than guessing a name.
        FlowStep(tool="create_encounter", from_step=0, from_field="name", ...),
        FlowStep(tool="assign_practitioner", from_step=1, from_field="name", ...),
    ),
    compensation=CompensationSpec(
        mechanism="reverse", undo_with=("cancel_encounter", "delete_patient")
    ),
)
```

## Every write says how it is undone

That is the rule this extension exists to demonstrate. A reversible action
names the tool that undoes it — and a test asserts that tool actually exists in
the registry, because a compensation that names a tool nobody registered is a
promise nobody can keep. An irreversible action says *why* it is irreversible,
rather than hiding behind prose.

## The agent

An extension is not only tools. A chat with nine healthcare tools and no agent
is a chat that will happily admit a patient to answer a question about opening
hours. `agent.py` carries the persona, four boundaries the agent will not
cross, and four prompts — two always-on, two selected by situation.

The core's assembler is deterministic and ordered: core prompt → active
extension's agent → its task prompts → conversation. Twenty extensions
contribute *content*; none contributes assembly logic.

## Testing

```bash
PYTHONPATH=.:../albanna-ai-chat python -m pytest tests/
```

The tests import the **real core** and run this manifest through the core's own
validator. That is the point: a reference extension that only tests itself
proves nothing about whether the seam works.

## License

MIT
