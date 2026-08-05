# --- file: core/automations_api_models.py ---
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.config import ActionConfig, ConditionConfig, EVENT_FAMILY_TO_ON_OFF, TriggerConfig


_NUMERIC_IDX_RE = re.compile(r"^\d+$")


class BranchedTriggerDevice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: str

    @model_validator(mode="after")
    def _validate_entity_id(self) -> "BranchedTriggerDevice":
        if _NUMERIC_IDX_RE.match(self.entity_id):
            raise ValueError("entity_id must not be a numeric idx")
        return self


class BranchedTriggerEventFamily(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # In Y1 branched YAML we store the event *family* here (not the concrete ON/OFF EventType key).
    event: str

    @model_validator(mode="after")
    def _validate_event_family(self) -> "BranchedTriggerEventFamily":
        if self.event not in EVENT_FAMILY_TO_ON_OFF:
            raise ValueError(f"Unsupported event family '{self.event}'")
        return self


class AutomationBranch(BaseModel):
    """
    Y1 branch payload: branch-level conditions + actions.
    """
    model_config = ConfigDict(extra="forbid")

    conditions: Optional[List[ConditionConfig]] = None
    actions: List[ActionConfig]

    @model_validator(mode="after")
    def _validate_branch_entity_ids(self) -> "AutomationBranch":
        # Ensure we never persist numeric idxs where entity_id is expected.
        for c in self.conditions or []:
            if c.entity_id and _NUMERIC_IDX_RE.match(c.entity_id):
                raise ValueError("condition.entity_id must not be a numeric idx")
        for a in self.actions:
            if a.entity_id and _NUMERIC_IDX_RE.match(a.entity_id):
                raise ValueError("action.entity_id must not be a numeric idx")
        return self


class BranchedAutomationRuleRequest(BaseModel):
    """
    Y1 stored shape for ON/OFF branched rules.
    """
    model_config = ConfigDict(extra="forbid")

    id: Optional[str] = None
    name: str
    scene: bool = False
    require_confirmation: bool = False
    trigger: Union[BranchedTriggerDevice, BranchedTriggerEventFamily]
    on: Optional[AutomationBranch] = None
    off: Optional[AutomationBranch] = None

    @model_validator(mode="after")
    def _require_one_branch(self) -> "BranchedAutomationRuleRequest":
        if self.on is None and self.off is None:
            raise ValueError("At least one of 'on' or 'off' must be provided.")
        return self


class FlatAutomationRuleRequest(BaseModel):
    """
    Flat stored shape (legacy / multi-trigger / condition-discriminated rules).
    SYNC mirrors are expanded to ON/OFF cases by schema v2 normalize.
    """
    model_config = ConfigDict(extra="forbid")

    id: Optional[str] = None
    name: str
    scene: bool = False
    require_confirmation: bool = False
    trigger: Union[TriggerConfig, List[TriggerConfig]]
    conditions: Optional[List[ConditionConfig]] = None
    actions: List[ActionConfig]

    @model_validator(mode="after")
    def _validate_flat_entity_ids(self) -> "FlatAutomationRuleRequest":
        triggers = self.trigger if isinstance(self.trigger, list) else [self.trigger]
        for t in triggers:
            if t.entity_id and _NUMERIC_IDX_RE.match(t.entity_id):
                raise ValueError("trigger.entity_id must not be a numeric idx")
        for c in self.conditions or []:
            if c.entity_id and _NUMERIC_IDX_RE.match(c.entity_id):
                raise ValueError("condition.entity_id must not be a numeric idx")
        for a in self.actions:
            if a.entity_id and _NUMERIC_IDX_RE.match(a.entity_id):
                raise ValueError("action.entity_id must not be a numeric idx")
        return self


class AutomationsRuleIdRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str

