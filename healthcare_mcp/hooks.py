"""Frappe app hooks — the one file Frappe reads to wire this app in.

This app is an *extension* to the frappe-mcp core.  It contributes tools, an
agent and prompts, and it is installed and uninstalled like any other Frappe
app — which is the whole point of using a Frappe hook rather than a Python
entry point.

The one line that matters
-------------------------
``frappe_mcp_tools`` points at this app's manifest module.  The core resolves
that hook **per site**, validates it atomically, and absorbs the tools tagged
with this app's name.  Install this app and the chat gains a healthcare agent
that knows about patients; uninstall it and those tools are gone, and only
those tools.

Why not a Python entry point
----------------------------
An entry point lives in the bench *virtualenv*, which every site on the bench
shares.  Install this extension there and its tools appear on every site
running the core — including sites that do not have this app installed, where
``Patient`` and ``Patient Encounter`` do not exist.  A Frappe hook is
site-scoped, and the scoping comes for free.
"""

app_name = "healthcare_mcp"
app_title = "Healthcare MCP"
app_publisher = "Albanna Software Solutions"
app_description = "Healthcare tools, agent and prompts for the frappe-mcp core."
app_email = "ahmedalbanna966@gmail.com"
app_license = "mit"

# This extension contributes tools to the core, so the core must be present.
required_apps = ["albanna_ai_chat"]

# --------------------------------------------------------------------------
# The extension seam.
#
# The value is a dotted path to a module carrying TOOLS and TIERS.  The core
# imports it, validates it atomically, and absorbs it.
# --------------------------------------------------------------------------

frappe_mcp_tools = "healthcare_mcp.tools.manifest"

# --------------------------------------------------------------------------
# The agent this extension brings.
#
# The core's prompt assembler reads this to build the system prompt when this
# extension's agent is the active one.  Pure data, so it is testable without
# a site.
# --------------------------------------------------------------------------

frappe_mcp_agent = "healthcare_mcp.agent"

# The installer creates the Single settings row so the extension is
# configurable the moment it is installed.
after_install = "healthcare_mcp.install.after_install"
