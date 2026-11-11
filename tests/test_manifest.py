"""The extension contract, validated against the real core.

These tests import ``albanna_ai_chat`` — the core — and run this extension's
manifest through the core's own validator.  That is the point: a reference
extension that only tests itself proves nothing about whether the seam works.

The core is expected on ``PYTHONPATH``; see ``pyproject.toml`` and the README.
"""

import pathlib
import sys

import pytest

# The core lives in a sibling checkout. Put it on the path rather than
# requiring an install, so these tests run from a fresh clone.
CORE = pathlib.Path(__file__).resolve().parent.parent.parent / "albanna-ai-chat"
if CORE.is_dir() and str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

albanna_ai_chat = pytest.importorskip("albanna_ai_chat")

from albanna_ai_chat.core.file_tools import CORE_TOOLS  # noqa: E402
from albanna_ai_chat.core.flow import MECHANISMS  # noqa: E402
from albanna_ai_chat.core.tools import READ, WRITE  # noqa: E402
from albanna_ai_chat.core.validate import (  # noqa: E402
    ContractViolation,
    absorb,
    validate_module,
)

from healthcare_mcp.agent import HEALTHCARE_AGENT, system_prompt  # noqa: E402
from healthcare_mcp.tools import manifest  # noqa: E402


def module():
    """This extension's manifest, as the core's validator expects it."""
    import types

    mod = types.ModuleType("healthcare_mcp.tools.manifest")
    mod.TOOLS = manifest.TOOLS
    mod.TIERS = manifest.TIERS
    return mod


@pytest.fixture(scope="module")
def specs():
    return validate_module(module(), known_tools=set(CORE_TOOLS.names()))


@pytest.fixture(scope="module")
def registry(specs):
    """The registry as the core's *loader* builds it.

    ``validate_module`` tags a spec with its module's name, which for a
    manifest at ``healthcare_mcp.tools.manifest`` would be ``"manifest"``.
    The loader re-tags with the *app* name, because an uninstall keys on the
    app — see ``albanna_ai_chat/services/extensions.py``. This fixture does
    the same, so it tests the path a real install takes rather than a
    convenient one.
    """
    from dataclasses import replace

    tagged = [replace(spec, source="healthcare_mcp") for spec in specs]
    return absorb(tagged, CORE_TOOLS)


# --------------------------------------------------------------------------
# The contract validates
# --------------------------------------------------------------------------


class TestTheContractValidates:
    def test_the_core_accepts_every_tool(self, specs):
        assert len(specs) == len(manifest.TOOLS)

    def test_every_tool_is_classified(self, specs):
        for spec in specs:
            assert spec.tier in (READ, WRITE), spec.name

    def test_tiers_and_tools_agree(self, specs):
        declared = {spec.name for spec in specs}
        assert declared == set(manifest.TIERS)

    def test_no_tool_shadows_a_core_tool(self, specs):
        core = set(CORE_TOOLS.names())
        assert not ({spec.name for spec in specs} & core)

    def test_absorption_is_atomic_and_returns_a_new_registry(self, registry):
        assert len(registry) == len(CORE_TOOLS) + len(manifest.TOOLS)
        assert len(CORE_TOOLS) == 3, "the core's own surface must not have grown"


# --------------------------------------------------------------------------
# Provenance — what makes an uninstall exact
# --------------------------------------------------------------------------


class TestProvenance:
    def test_every_tool_is_tagged_with_this_app(self, registry):
        assert [s.name for s in registry.from_source("healthcare_mcp")] == [
            spec.name for spec in manifest.TOOLS
        ]

    def test_the_core_tools_keep_their_own_tag(self, registry):
        assert [s.name for s in registry.from_source("core")] == list(CORE_TOOLS.names())

    def test_uninstalling_removes_exactly_these_tools(self, registry):
        from albanna_ai_chat.core.toolset import without_source

        remaining = without_source(registry, "healthcare_mcp")
        assert set(remaining.names()) == set(CORE_TOOLS.names())


# --------------------------------------------------------------------------
# Every write says how it is undone
# --------------------------------------------------------------------------


class TestCompensation:
    def test_every_write_declares_one(self, specs):
        for spec in specs:
            if not spec.mutating:
                continue
            if spec.is_flow:
                assert spec.flow.compensation is not None, spec.name
            else:
                assert spec.compensation is not None, spec.name

    def test_every_mechanism_is_one_the_core_knows(self, specs):
        for spec in specs:
            declarations = []
            if spec.compensation is not None:
                declarations.append(spec.compensation)
            if spec.is_flow:
                declarations.append(spec.flow.compensation)
            for declaration in declarations:
                assert declaration.mechanism in MECHANISMS, spec.name

    def test_an_irreversible_action_says_why(self, specs):
        for spec in specs:
            declarations = []
            if spec.compensation is not None:
                declarations.append(spec.compensation)
            if spec.is_flow:
                declarations.append(spec.flow.compensation)
            for declaration in declarations:
                if declaration.mechanism == "none":
                    assert declaration.reason.strip(), (
                        f"{spec.name} is irreversible and must say why"
                    )

    def test_a_reversible_action_names_the_tool_that_undoes_it(self, specs):
        for spec in specs:
            declarations = []
            if spec.compensation is not None:
                declarations.append(spec.compensation)
            if spec.is_flow:
                declarations.append(spec.flow.compensation)
            for declaration in declarations:
                if declaration.mechanism != "none":
                    assert declaration.undo_with, (
                        f"{spec.name} claims {declaration.mechanism} but names no tool"
                    )

    def test_the_undo_tools_actually_exist(self, registry):
        """A compensation that names a tool nobody registered is a promise
        nobody can keep."""
        for spec in registry.all():
            declarations = []
            if spec.compensation is not None:
                declarations.append(spec.compensation)
            if spec.is_flow:
                declarations.append(spec.flow.compensation)
            for declaration in declarations:
                for tool in declaration.undo_with:
                    assert tool in registry, f"{spec.name} undoes with unknown {tool}"


# --------------------------------------------------------------------------
# The flow
# --------------------------------------------------------------------------


class TestTheFlow:
    def test_there_is_exactly_one(self, specs):
        flows = [spec for spec in specs if spec.is_flow]
        assert [spec.name for spec in flows] == ["admit_patient"]

    def test_the_ratio_is_not_one_flow_per_tool(self, specs):
        """erpnext-mcp ships 451 tools and eleven flows. A rule that turns
        every tool into a flow is not that ratio."""
        flows = sum(1 for spec in specs if spec.is_flow)
        assert flows < len(specs) / 2

    def test_it_has_at_least_two_steps(self, specs):
        flow = next(spec for spec in specs if spec.is_flow)
        assert len(flow.flow.steps) >= 2

    def test_every_step_names_a_registered_tool(self, registry):
        flow = registry.get("admit_patient")
        for step in flow.flow.steps:
            assert step.tool in registry, step.tool

    def test_a_step_consumes_an_earlier_step_output(self, registry):
        """That is what makes a flow a pipeline rather than a script with
        constants in it."""
        flow = registry.get("admit_patient")
        consuming = [s for s in flow.flow.steps if s.from_step is not None]
        assert consuming, "no step consumes another's output"
        for step in consuming:
            assert 0 <= step.from_step < flow.flow.steps.index(step)

    def test_the_flow_declares_no_problems(self, registry):
        flow = registry.get("admit_patient")
        assert flow.flow.problems() == []


# --------------------------------------------------------------------------
# The validator actually refuses things
# --------------------------------------------------------------------------


class TestTheValidatorRefuses:
    def test_an_unclassified_tool(self):
        import types

        mod = types.ModuleType("broken")
        mod.TOOLS = [manifest.LIST_PATIENTS]
        mod.TIERS = {}
        with pytest.raises(ContractViolation):
            validate_module(mod, known_tools=set(CORE_TOOLS.names()))

    def test_a_collision_with_a_core_tool(self):
        import types

        mod = types.ModuleType("shadow")
        mod.TOOLS = [manifest.LIST_PATIENTS]
        mod.TIERS = {"list_patients": READ}
        # Rename it onto a core tool's name.
        shadow = type(manifest.LIST_PATIENTS)(
            name="read_file",
            description=manifest.LIST_PATIENTS.description,
            parameters=manifest.LIST_PATIENTS.parameters,
            tier=READ,
        )
        mod.TOOLS = [shadow]
        with pytest.raises(ContractViolation):
            validate_module(mod, known_tools=set(CORE_TOOLS.names()))

    def test_a_sql_parameter(self):
        import types

        bad = type(manifest.LIST_PATIENTS)(
            name="run_sql",
            description="Run SQL.",
            parameters={
                "type": "object",
                "additionalProperties": False,
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
            tier=READ,
        )
        mod = types.ModuleType("sqlful")
        mod.TOOLS = [bad]
        mod.TIERS = {"run_sql": READ}
        with pytest.raises(ContractViolation) as excinfo:
            validate_module(mod, known_tools=set(CORE_TOOLS.names()))
        assert "sql" in str(excinfo.value)


# --------------------------------------------------------------------------
# The agent
# --------------------------------------------------------------------------


class TestTheAgent:
    def test_it_has_a_purpose_and_a_persona(self):
        assert HEALTHCARE_AGENT.purpose.strip()
        assert HEALTHCARE_AGENT.persona.strip()

    def test_it_states_what_it_will_not_do(self):
        """A refusal the model can act on is worth more than a permission it
        cannot."""
        assert len(HEALTHCARE_AGENT.boundaries) >= 3

    def test_the_system_prompt_is_deterministic(self):
        assert system_prompt() == system_prompt()

    def test_the_system_prompt_carries_the_boundaries(self):
        text = system_prompt()
        for line in HEALTHCARE_AGENT.boundaries:
            assert line in text

    def test_the_always_on_prompts_are_in_it(self):
        text = system_prompt()
        for prompt in HEALTHCARE_AGENT.prompts_for("always"):
            assert prompt.text in text

    def test_a_conditional_prompt_is_not_in_it(self):
        """A prompt nobody needs is a prompt that dilutes the ones that do."""
        text = system_prompt()
        conditional = [p for p in HEALTHCARE_AGENT.prompts if p.when != "always"]
        for prompt in conditional:
            assert prompt.text not in text

    def test_a_conditional_prompt_is_selected_when_it_applies(self):
        chosen = HEALTHCARE_AGENT.prompts_for("admit_patient")
        assert any(p.name == "admission_is_one_step" for p in chosen)
