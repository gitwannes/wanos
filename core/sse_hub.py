# --- file: core/sse_hub.py ---
"""
B10H: event-driven SSE — push domain deltas on state queue drain (no poll loop).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Set

from .models import SystemState

# Domains streamed to wanosApp / zwaveconfig SSE clients (same set as legacy poll loop).
SSE_DOMAIN_KEYS: tuple[str, ...] = (
    "system",
    "sensors",
    "sauna",
    "ir",
    "metrics",
    "hardware",
    "devices",
    "device_metadata",
)


@dataclass(eq=False)
class SseClient:
    """One browser EventSource connection.

    eq=False: identity hash so the hub can keep clients in a set.
    Default dataclass eq (unfrozen) sets __hash__ = None → TypeError on subscribe.
    """

    queue: asyncio.Queue[str] = field(default_factory=lambda: asyncio.Queue(maxsize=256))
    last_domain_snapshots: dict[str, str] = field(default_factory=dict)


class SseHub:
    """Fan-out SSE lines to connected clients when state domains change."""

    def __init__(self) -> None:
        self._clients: set[SseClient] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> SseClient:
        client = SseClient()
        async with self._lock:
            self._clients.add(client)
        return client

    async def unsubscribe(self, client: SseClient) -> None:
        async with self._lock:
            self._clients.discard(client)

    async def broadcast(self, snapshot_obj: SystemState, changed_domains: Set[str]) -> None:
        """Enqueue SSE data lines for domains that changed (per-client diff)."""
        if not changed_domains:
            return
        async with self._lock:
            if not self._clients:
                return
            clients = list(self._clients)

        for client in clients:
            for domain in changed_domains:
                if domain not in SSE_DOMAIN_KEYS:
                    continue
                domain_data: Any = getattr(snapshot_obj, domain, None)
                if domain_data is None:
                    continue
                if hasattr(domain_data, "model_dump"):
                    domain_json = json.dumps(domain_data.model_dump(), default=str)
                else:
                    domain_json = json.dumps(domain_data, default=str)
                if client.last_domain_snapshots.get(domain) == domain_json:
                    continue
                client.last_domain_snapshots[domain] = domain_json
                payload = json.dumps({"domain": domain, "data": json.loads(domain_json)})
                line = f"data: {payload}\n\n"
                try:
                    client.queue.put_nowait(line)
                except asyncio.QueueFull:
                    # Slow consumer — drop delta; client still has REST snapshot + pings.
                    pass

    async def broadcast_payload(self, domain: str, data: Any) -> None:
        """
        Push one domain payload (not a SystemState snapshot).
        C18: per-idx apply/revert (`c18_commit` + `devices`) after request success/fail.
        """
        payload = json.dumps({"domain": domain, "data": data}, default=str)
        line = f"data: {payload}\n\n"
        async with self._lock:
            clients = list(self._clients)
        for client in clients:
            try:
                client.queue.put_nowait(line)
            except asyncio.QueueFull:
                pass


# Process-wide hub wired from main.py → StateManager._sse_hub
sse_hub = SseHub()
