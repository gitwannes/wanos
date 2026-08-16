# --- file: core/command_commit.py ---
"""
C18: request-level success/fail for Explorer Control (locked Q4/Q5).

Outbound I/O runs in create_task (drain must not await Hue PUT / MQTT / TCP).
Sibling SSE holds old_val until success or 0.5 s. Fail before that: do not reveal.
Fail after reveal: snap RAM + UI, error bell, app-log ERROR. Unclaimed = fail.
"""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger as system_logger

from core.models import format_device_ref
from logic.alert_manager import AlertManager

# Operator lock: reveal RAM at 0.5 s if the request has not failed yet.
COMMIT_HOLD_SECS: float = 0.5

# Inbound echoes must not open a commit hold (would delay live telemetry).
_INBOUND_ORIGINS = frozenset({"hue", "zwave", "sonos", "onkyo"})


def is_outbound_hub_command(payload: Optional[dict]) -> bool:
    """True when HUB_STATE_CHANGED is a WanOS-originated command, not a bridge echo."""
    if not payload:
        return False
    if payload.get("is_initialization"):
        return False
    origin = str(payload.get("origin") or "").strip().lower()
    if origin in _INBOUND_ORIGINS:
        return False
    if payload.get("rfx_origin") is not None:
        return False
    # Onkyo handshake / cache-invalidation dispatches use origin=system.
    if origin == "system":
        return False
    return True


def token_from_payload(payload: Optional[dict]) -> Any:
    """C18 token stamped on outbound HUB_STATE_CHANGED payloads."""
    if not payload:
        return None
    return payload.get("_c18_token")


def claim_and_finish(manager: Any, payload: Optional[dict], ok: bool, reason: str = "") -> None:
    """Claim (if not already) and report success/fail for a C18 token on payload."""
    commit = getattr(manager, "command_commit", None)
    if commit is None or not payload:
        return
    idx = payload.get("idx")
    token = token_from_payload(payload)
    if token is None:
        return
    commit.claim(idx, token)
    if ok:
        commit.report_success(idx, token)
    else:
        commit.report_fail(idx, token, reason)


def claim_payload(manager: Any, payload: Optional[dict]) -> bool:
    """Claim outbound send for this payload's C18 token."""
    commit = getattr(manager, "command_commit", None)
    if commit is None or not payload:
        return False
    return commit.claim(payload.get("idx"), token_from_payload(payload))


def _attempted_label(state_val: Any) -> str:
    """Bell/log arrow target (ON / OFF / numeric level)."""
    if isinstance(state_val, dict):
        inner = state_val.get("state")
        if inner is not None:
            return str(inner)
    if state_val is None:
        return "?"
    return str(state_val)


@dataclass
class PendingCommand:
    """One idx waiting for request-level success/fail (C18)."""

    idx: int
    old_val: Any
    attempted: str
    token: int
    deadline: float
    claimed: bool = False
    applied: bool = False
    success: bool = False
    failed: bool = False
    reason: str = ""
    event: asyncio.Event = field(default_factory=asyncio.Event)


class CommandCommit:
    """
    Per-idx request success/fail watcher. StateManager owns one instance.
    Senders claim + report; the event worker never awaits integration I/O.
    """

    def __init__(self, manager: Any) -> None:
        self._manager = manager
        self._pending: Dict[int, PendingCommand] = {}
        self._seq: int = 0
        self._watch_task: Optional[asyncio.Task] = None
        self._wake: asyncio.Event = asyncio.Event()

    def register(self, idx: Optional[int], old_val: Any, state_val: Any) -> Optional[int]:
        """Start a hold for idx. Returns token for claim/report, or None if idx missing."""
        if idx is None:
            return None
        self._seq += 1
        token = self._seq
        try:
            now = asyncio.get_running_loop().time()
        except RuntimeError:
            now = 0.0
        self._pending[int(idx)] = PendingCommand(
            idx=int(idx),
            old_val=copy.deepcopy(old_val),
            attempted=_attempted_label(state_val),
            token=token,
            deadline=now + COMMIT_HOLD_SECS,
        )
        self._wake.set()
        return token

    def claim(self, idx: Optional[int], token: Any) -> bool:
        """Mark that an integration is actually sending this command."""
        p = self._get(idx, token)
        if p is None:
            return False
        p.claimed = True
        return True

    def report_success(self, idx: Optional[int], token: Any) -> None:
        p = self._get(idx, token)
        if p is None or p.failed:
            return
        p.success = True
        p.event.set()

    def report_fail(self, idx: Optional[int], token: Any, reason: str) -> None:
        p = self._get(idx, token)
        if p is None or p.success:
            return
        p.failed = True
        p.reason = reason or "command failed"
        p.event.set()

    def _get(self, idx: Optional[int], token: Any) -> Optional[PendingCommand]:
        if idx is None or token is None:
            return None
        try:
            tok = int(token)
        except (TypeError, ValueError):
            return None
        p = self._pending.get(int(idx))
        if p is None or p.token != tok:
            return None
        return p

    def hold_pending_on_snapshot(self, snapshot: Any) -> None:
        """
        Q4/Q5: devices SSE/REST for in-flight idxs stay at old_val until apply.
        Mutates a deep-copied snapshot only — live RAM already has the new value.
        """
        devices = getattr(snapshot, "devices", None)
        if not devices:
            return
        for idx, p in list(self._pending.items()):
            if p.applied or p.failed:
                continue
            held = copy.deepcopy(p.old_val)
            devices[idx] = held
            if str(idx) in devices:
                devices[str(idx)] = held

    def fail_unclaimed(self) -> None:
        """Silent skip / no integration sent → fail (locked C18 Q4)."""
        for p in list(self._pending.values()):
            if not p.claimed and not p.success and not p.failed:
                p.failed = True
                p.reason = "not sent (unmapped, disabled, or empty payload)"
                p.event.set()

    def arm_watch(self) -> None:
        """Watch in-flight commands without blocking the event worker."""
        if not self._pending:
            return
        if self._watch_task is not None and not self._watch_task.done():
            self._wake.set()
            return
        # Bind Event to this loop (avoid a __init__ Event from another loop hanging waits).
        self._wake = asyncio.Event()
        self._watch_task = asyncio.create_task(self._watch_loop())

    async def _wait_reports(self, cmds: List[PendingCommand], timeout: Optional[float]) -> None:
        """Wait until a report, a new register (_wake), or timeout. Cancel leftover waiters."""
        self._wake.clear()
        tasks = [asyncio.create_task(p.event.wait()) for p in cmds]
        tasks.append(asyncio.create_task(self._wake.wait()))
        try:
            await asyncio.wait(
                tasks,
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _watch_loop(self) -> None:
        """Reveal RAM on success or at that idx's 0.5 s; revert + bell on fail after reveal."""
        try:
            while True:
                await self._process_reports()
                self._gc()
                if not self._pending:
                    return

                now = asyncio.get_running_loop().time()
                for p in list(self._pending.values()):
                    if p.failed or p.applied:
                        continue
                    # Unclaimed = not sent. Fail at 0.5 s (not at drain) so SSE already showed RAM.
                    if now >= p.deadline and not p.claimed and not p.success:
                        p.failed = True
                        p.reason = "not sent (unmapped, disabled, or empty payload)"
                        p.event.set()
                        continue
                    if p.success or now >= p.deadline:
                        await self._apply(p)

                await self._process_reports()
                self._gc()
                if not self._pending:
                    return

                waiters = [
                    p for p in self._pending.values()
                    if not p.failed and not (p.success and p.applied)
                ]
                if not waiters:
                    continue

                hold_remaining: List[float] = []
                for p in waiters:
                    if not p.applied and not p.success and not p.failed:
                        hold_remaining.append(max(0.0, p.deadline - asyncio.get_running_loop().time()))
                timeout: Optional[float] = min(hold_remaining) if hold_remaining else None
                await self._wait_reports(waiters, timeout=timeout)
        except Exception as e:
            system_logger.error(f"[C18] command commit watch failed: {e}")

    async def _process_reports(self) -> None:
        for p in list(self._pending.values()):
            if p.success and not p.applied:
                await self._apply(p)
            elif p.failed:
                await self._on_fail(p)

    def _device_value(self, idx: int) -> Any:
        """RAM lookup — live devices may be keyed as int or str."""
        devices = self._manager._state.devices or {}
        if idx in devices:
            return devices[idx]
        return devices.get(str(idx))

    async def _apply(self, p: PendingCommand) -> None:
        if p.applied or p.failed:
            return
        p.applied = True
        await self._push_idx(p.idx, self._device_value(p.idx), force=True)

    async def _on_fail(self, p: PendingCommand) -> None:
        """Restore RAM. Force-push old so siblings stay old and the optimistic click snaps back."""
        old = copy.deepcopy(p.old_val)
        self._manager._state.devices[p.idx] = old
        if str(p.idx) in (self._manager._state.devices or {}):
            self._manager._state.devices[str(p.idx)] = old
        await self._push_idx(p.idx, old, force=True)
        await self._bell_and_log(p)
        self._pending.pop(p.idx, None)

    async def _bell_and_log(self, p: PendingCommand) -> None:
        ref = format_device_ref(self._manager._state, p.idx)
        bell = f"ERROR: Command failed: {ref} → {p.attempted}"
        log_line = f"{bell} {p.reason}".strip()
        await self._manager.logger.error(log_line)
        ch, domains = AlertManager.process_alert(self._manager._state, bell)
        if ch and self._manager._sse_hub is not None:
            try:
                await self._manager._sse_hub.broadcast(self._manager._state, domains)
            except Exception as e:
                system_logger.error(f"[C18] fail alert SSE: {e}")

    async def _push_idx(self, idx: int, value: Any, force: bool = False) -> None:
        """
        SSE one device key. `c18_commit` bypasses Explorer uiLocks (clicked snap-back).
        Also push `devices` so Control `item.is_on` and non-Explorer SSE clients update.
        """
        hub = self._manager._sse_hub
        if hub is None:
            return
        data = {str(idx): value}
        try:
            if force:
                await hub.broadcast_payload("c18_commit", data)
            await hub.broadcast_payload("devices", data)
        except Exception as e:
            system_logger.error(f"[C18] push idx {idx}: {e}")

    def _gc(self) -> None:
        """Drop finished holds so later SSE/REST are live RAM."""
        self._pending = {
            i: p for i, p in self._pending.items()
            if not p.failed and not (p.success and p.applied)
        }
