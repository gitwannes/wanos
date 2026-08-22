# --- file: core/automation_limits.py ---
"""Shared automation authoring limits (B22 Then nesting, H4 Logic depth)."""

from __future__ import annotations

# Max nesting depth for B22 ``then:`` wrappers and H4 ``op: and|or|not`` groups.
MAX_NEST_DEPTH: int = 3
