# Changelog

All notable changes to Healthcare MCP are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the app uses [semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] — 2026-11-12

### Added

**The core version range this extension is built against.**

- `tools/manifest.py` — `REQUIRES_CORE = ">=0.1.0,<0.2.0"`. The core reads it
  and checks it against *activation*, not installation: an extension whose
  range excludes the running core is reported as incompatible and refused
  activation, which is a visible Settings row rather than a runtime surprise.
- The range pins to the core's minor because the core is pre-1.0 and its
  contract is not yet frozen. Widening it to `<1.0.0` would promise a
  stability the core has not earned; when the core reaches 1.0.0 this becomes
  `>=1.0.0,<2.0.0` and the widening is a real event.

## [0.1.0] — 2026-11-11

### Added

**The reference extension for the frappe-mcp core.**

- `tools/manifest.py` — nine tools and one flow, declared as the contract.
  Imports no Frappe, so the core can validate it on a machine with none of
  this app's dependencies installed.
- `tools/patient.py` — the Frappe handlers. The only module here that imports
  Frappe.
- `agent.py` — the agent: persona, four boundaries, four prompts (two
  always-on, two selected by situation), and a deterministic `system_prompt()`.
- `hooks.py` — `frappe_mcp_tools` points at the manifest; `frappe_mcp_agent`
  points at the agent.
- Doctypes: `Patient`, `Patient Encounter`, `Healthcare MCP Settings`.
- `install.py` — creates the `Healthcare MCP User` role and the Single
  settings row, idempotently, so a restored site repairs itself on the next
  migrate.
- `tests/test_manifest.py` — 29 tests that import the **real core** and run
  this manifest through the core's own validator.

### The decisions it demonstrates

- **A Frappe hook, not a Python entry point.** An entry point lives in the
  bench virtualenv every site shares, so its tools would appear on sites that
  do not have this app installed. A hook is site-scoped.
- **Nine tools, one flow.** `erpnext-mcp` ships 451 tools and eleven flows;
  a rule that turns every tool into a flow is not that ratio.
- **Every write declares its compensation**, and a test asserts the tool it
  names actually exists in the registry.
- **The core owns the authority layer.** These handlers never decide who may
  call them; the core removes a write tool from the model's view when the
  caller holds no such right anywhere.

### Notes

- The handlers and doctypes are written but have not been installed on a site.
  The contract — which is the part that must be right before anything else
  exists — is tested against the real core.
