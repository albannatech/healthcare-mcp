"""The Healthcare MCP module — the DocTypes this extension owns.

This file exists because Frappe resolves a module as
``<app_name>.<module_name>`` and reads its ``__file__`` to find the doctype
folder.  A module directory without an ``__init__.py`` is a *namespace*
package, whose ``__file__`` is ``None`` — and ``sync_for`` then fails with
``TypeError: expected str, bytes or os.PathLike object, not NoneType``.

That failure happens at install time and nowhere earlier, which is why the
Frappe-free test suite never caught it: the tests validate the manifest, and
the manifest is not the module.
"""
