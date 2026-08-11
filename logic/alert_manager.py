# --- file: logic/alert_manager.py ---
import uuid
from datetime import datetime
from typing import Optional, Set, Tuple
from core.models import SystemState


class AlertManager:
    """
    Centralized UI Notification Engine.
    Handles timestamping, deduplication, and severity classification for banner + bell.
    Banner = critical only; error/warning/success/info are bell-only.
    """

    @staticmethod
    def process_alert(state: SystemState, *msgs: Optional[str], domain: str = "system") -> Tuple[bool, Set[str]]:
        """
        Safely timestamps, deduplicates, and structures UI alerts into routing dictionaries.
        Auto-classifies severity based on emojis / keywords to maintain backwards compatibility
        with all existing alert strings across the architecture.

        UI levels: critical (banner + bell), error / warning / success / info (bell only).
        Returns (state_changed: bool, changed_domains: Set[str])
        """
        changed = False
        domains: Set[str] = set()

        for raw_msg in msgs:
            if not raw_msg:
                continue

            # Auto-classify severity and strip visual indicators for clean JSON delivery.
            # Order matters: CRITICAL / 🚨 before ERROR so banner emergencies stay critical;
            # ERROR before bare 🔴 so connection-transition alerts can be bell-only.
            level = "info"
            clean_msg = raw_msg
            upper_msg = raw_msg.upper()

            if "🚨" in raw_msg or "CRITICAL" in upper_msg:
                level = "critical"
                clean_msg = clean_msg.replace("🔴", "").replace("🚨", "")
                clean_msg = clean_msg.replace("CRITICAL:", "").replace("CRITICAL", "")
            elif "ERROR:" in upper_msg:
                # Explicit ERROR: prefix → bell-only (banner is critical-only).
                level = "error"
                for token in ("ERROR:", "Error:", "error:"):
                    clean_msg = clean_msg.replace(token, "")
                clean_msg = clean_msg.replace("🔴", "")
            elif "🔴" in raw_msg:
                level = "critical"
                clean_msg = clean_msg.replace("🔴", "")
            elif "🟡" in raw_msg or "⚠️" in raw_msg:
                level = "warning"
                clean_msg = clean_msg.replace("🟡", "").replace("⚠️", "")
            elif "🟢" in raw_msg or "SUCCESS" in upper_msg:
                level = "success"
                clean_msg = clean_msg.replace("🟢", "").replace("SUCCESS:", "").replace("SUCCESS", "")

            # Strip out common UI formatting emojis so the text looks perfectly clean in the toast notification
            for emoji in ["⚪", "🔵", "ℹ️", "🧹", "🔄", "🚀", "⏳"]:
                clean_msg = clean_msg.replace(emoji, "")

            clean_msg = clean_msg.strip()

            timestamp: str = datetime.now().strftime("%d %b %H:%M:%S")
            msg_handled = False

            # Prevent spam & increment counter: Check if base message is already active
            for existing in state.system.system_alert_msgs:
                if existing.get("message") == clean_msg:
                    existing["count"] = existing.get("count", 1) + 1
                    existing["timestamp"] = timestamp  # Refresh UI time on re-occurrence
                    changed = True
                    domains.add(domain)
                    msg_handled = True
                    break

            # Brand new message: Append as structured dictionary!
            if not msg_handled:
                state.system.system_alert_msgs.append({
                    "id": str(uuid.uuid4())[:8],
                    "level": level,
                    "message": clean_msg,
                    "timestamp": timestamp,
                    "count": 1
                })
                changed = True
                domains.add(domain)

        return changed, domains

    @staticmethod
    def dismiss_alert(state: SystemState, alert_id: str) -> bool:
        """Removes a specific alert by its UUID."""
        original_len = len(state.system.system_alert_msgs)
        state.system.system_alert_msgs = [
            msg for msg in state.system.system_alert_msgs
            if msg.get("id") != alert_id
        ]
        return len(state.system.system_alert_msgs) != original_len

    @staticmethod
    def clear_non_critical(state: SystemState) -> bool:
        """Wipes success/info/warning/error alerts, leaving only banner-critical entries."""
        original_len = len(state.system.system_alert_msgs)
        state.system.system_alert_msgs = [
            msg for msg in state.system.system_alert_msgs
            if msg.get("level") == "critical"
        ]
        return len(state.system.system_alert_msgs) != original_len