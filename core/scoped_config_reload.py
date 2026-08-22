# --- file: core/scoped_config_reload.py ---
"""B23: fast CONFIG_RELOAD paths for automations and events scopes."""

from __future__ import annotations

from typing import Any, List

from core.automations_store import read_automations
from core.config import AutomationRuleConfig, _expand_branched_automations_for_engine
from logic.automation_rules import AutomationEngine


def reload_automations_scope(manager: Any) -> None:
    """Re-read automation rules from disk into runtime config (no bridge recycle)."""
    raw = read_automations()
    expanded = _expand_branched_automations_for_engine(raw)
    rules: List[AutomationRuleConfig] = []
    for item in expanded:
        if not isinstance(item, dict):
            continue
        rules.append(AutomationRuleConfig.model_validate(item))
    manager._config.automations = rules
    AutomationEngine._config = None


def reload_events_scope(manager: Any) -> None:
    """Refresh events catalog RAM (dashboard buttons + history labels)."""
    manager._extract_scenes_from_config()
