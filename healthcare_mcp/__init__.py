"""Healthcare MCP — a reference extension for the frappe-mcp core.

This app is the worked example every other `-mcp` repo is generated from. It
proves the whole extension contract end to end: tools contributed through the
``frappe_mcp_tools`` hook, permissions declared and enforced by the core, a
configuration doctype, an agent with its prompts, and one genuine
transactional flow with a real compensation path.

It is deliberately small. Nine tools, one flow, two doctypes. A reference
that is not small is a reference nobody reads.
"""

__version__ = "0.1.1"
