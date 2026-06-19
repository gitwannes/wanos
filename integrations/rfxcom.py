# --- file: integrations/rfxcom.py ---
import asyncio
from typing import Any, Dict, Optional

from core.models import Event, EventType, SystemState
from core.state_manager import StateManager
from core.logger import WanosComponent

# 🛡️ Safe Import: Allows WanOS to boot even if pyRFXtrx is not yet installed
try:
    import RFXtrx
    import RFXtrx.lowlevel as lowlevel

    PYRFXTRX_AVAILABLE = True
except ImportError:
    PYRFXTRX_AVAILABLE = False


class NativeRFXCOMBridge(WanosComponent):
    def __init__(self, state_manager: StateManager, serial_port: str) -> None:
        super().__init__(state_manager)

        self.serial_port: str = serial_port
        self.core: Optional[Any] = None
        self._integration_enabled: bool = False

        # Reference to the main asyncio loop so the background serial thread can safely call back into it
        self.loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

        # The internal circuit-breaker cache.
        # Tracks the physical state to instantly drop network echoes.
        self._last_known_states: Dict[int, str] = {}

        # ⚡ INBOUND EDGE MAP: hex_id -> {"idx": 40001, "state": "ON"}
        self._inbound_map: Dict[str, Dict[str, Any]] = {}

        # ⚡ OUTBOUND EDGE MAP: idx -> {"protocol": "Lighting4", "ON": "544555", "OFF": "544554"}
        self._outbound_map: Dict[int, Dict[str, str]] = {}

        self._build_translation_maps()

    def _build_translation_maps(self) -> None:
        """Parses the config.yaml block to construct O(1) lookup tables for lightning-fast packet translation."""
        if not hasattr(self.state_manager._config, "native_rfx"):
            return

        for device in self.state_manager._config.native_rfx:
            idx = device.virtual_idx

            # Map for out-bound transmission lookups
            self._outbound_map[idx] = {
                "protocol": device.protocol,
                "ON": device.on_id.strip().lower(),
                "OFF": device.off_id.strip().lower()
            }

            # Map for in-bound reception lookups
            self._inbound_map[device.on_id.strip().lower()] = {"idx": idx, "state": "ON"}
            self._inbound_map[device.off_id.strip().lower()] = {"idx": idx, "state": "OFF"}

    async def start(self) -> None:
        """Initializes the physical USB connection and spawns the background listener thread."""
        if not PYRFXTRX_AVAILABLE:
            await self.logger.critical("[Native RFX] pyRFXtrx library is not installed. Aborting hardware mount.")
            return

        self._integration_enabled = self.state_manager._state.system.rfxcom_integration_enabled
        self.state_manager.register_listener(self._on_state_changed)

        try:
            # ⚡ PyRFXtrx natively spawns a background thread to read the serial stream!
            # We supply self._rfx_callback as the hook for when a packet successfully decodes.
            await self.logger.info(f"[Native RFX] Mounting physical USB Transceiver on {self.serial_port}...")

            # Run the blocking core initialization in an executor so it doesn't freeze the boot sequence
            self.core = await self.loop.run_in_executor(
                None,
                lambda: RFXtrx.Core(
                    self.serial_port,
                    transport_protocol=RFXtrx.PySerialTransport,
                    event_callback=self._rfx_callback
                )
            )

            # Tell the StateManager the hardware is alive
            self.is_connected = True
            await self.logger.success("[Native RFX] USB Transceiver mounted successfully. Listener thread active.")

        except Exception as e:
            self.is_connected = False
            await self.logger.error(f"[Native RFX] Failed to mount USB Transceiver: {e}")

    async def stop(self) -> None:
        """Gracefully closes the USB port and terminates the background thread."""
        self.is_connected = False
        if self.core and self.core.transport:
            try:
                # Close the physical serial port
                await self.loop.run_in_executor(None, self.core.transport.close)
                await self.logger.warning("[Native RFX] USB Transceiver unmounted and released.")
            except Exception as e:
                await self.logger.error(f"[Native RFX] Error closing USB Transceiver: {e}")

    # =========================================================================
    # INBOUND EDGE (Reading the Airwaves)
    # =========================================================================

    def _rfx_callback(self, event: Any) -> None:
        """
        ⚡ WARNING: This method executes inside the pyRFXtrx background C-thread! ⚡
        You cannot safely modify WanOS state or log async messages from here.
        We must extract the raw data and bounce it back to the main asyncio loop immediately.
        """
        if not hasattr(event, "device") or not hasattr(event.device, "id_string"):
            return

        # Clean the ID string (pyRFXtrx sometimes outputs "13_00_54_45_55" depending on the sub-protocol)
        raw_id = str(event.device.id_string).lower().replace("_", "")

        # Teleport execution safely back to the WanOS event loop!
        self.loop.call_soon_threadsafe(self._process_inbound_threadsafe, raw_id)

    def _process_inbound_threadsafe(self, raw_id: str) -> None:
        """
        Executes on the primary asyncio loop.
        Maps the raw hex ID to a virtual IDX and dispatches it to the WanOS Engine.
        """
        # Master integration kill-switch check
        if not self._integration_enabled:
            return

        # Scan our inbound map to see if we recognize this hex code
        for configured_hex, mapping in self._inbound_map.items():
            if configured_hex in raw_id:
                virtual_idx = mapping["idx"]
                target_state = mapping["state"]

                # ⚡ 100% DETERMINISTIC ECHO DROP
                # If the physical cache is already perfectly aligned with this state,
                # we silently drop the packet to prevent infinite engine ping-pong loops.
                if self._last_known_states.get(virtual_idx) == target_state:
                    return

                # Synchronize local circuit breaker cache
                self._last_known_states[virtual_idx] = target_state

                # Look up the semantic name for clean UI hybrid learning
                virtual_name = self.state_manager._config.dashboard.get(virtual_idx, f"idx_{virtual_idx}")

                # ⚡ ORIGIN TAGGING
                # We tag this event with 'rfx_origin'. This tells the outbound edge router
                # that the physical light is ALREADY on, so it shouldn't blast a duplicate radio command.
                self.state_manager.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={
                        "idx": virtual_idx,
                        "state": target_state,
                        "name": virtual_name,
                        "is_push_button": False,
                        "rfx_origin": configured_hex
                    }
                ))

                # We use create_task here because we are in a synchronous threadsafe wrapper
                asyncio.create_task(self.logger.debug(
                    f"[Native RFX] Physical Remote Intercepted: Hex [{configured_hex}] mapped to Virtual IDX {virtual_idx} -> {target_state}"))
                return

    # =========================================================================
    # OUTBOUND EDGE (Transmitting to the Airwaves)
    # =========================================================================

    async def _on_state_changed(self, state: SystemState, events: list[Event] = None) -> None:
        """Listens to the WanOS Engine and broadcasts state mutations out via the USB antenna."""

        # --- Master Toggle State Evaluation ---
        current_enabled = state.system.rfxcom_integration_enabled
        if current_enabled and not getattr(self, '_integration_enabled', False):
            self._integration_enabled = True
            await self.logger.success("[Native RFX] Engine ENABLED via UI.")
        elif not current_enabled and getattr(self, '_integration_enabled', False):
            self._integration_enabled = False
            await self.logger.info("[Native RFX] Engine DISABLED via UI.")

        if not current_enabled or not getattr(self, 'is_connected', False):
            return

        # --- Process Batch Events ---
        if events:
            for event in events:
                if event.type == EventType.HUB_STATE_CHANGED:
                    idx = event.payload.get("idx")
                    new_state = event.payload.get("state")
                    rfx_origin = event.payload.get("rfx_origin")
                    is_init = event.payload.get("is_initialization", False)

                    # Ensure this is actually a device managed by the Native RFX block
                    if idx in self._outbound_map:

                        # Only proceed if the state actually mutated
                        if new_state != self._last_known_states.get(idx):

                            # 1. Deterministic Boot Absorber
                            if is_init:
                                self._last_known_states[idx] = new_state
                                continue

                            # 2. Sync the local physical cache
                            self._last_known_states[idx] = new_state

                            # 3. Origin Router: Only transmit if the command came from the UI or Automation Engine
                            # If rfx_origin is populated, it means the physical remote triggered it, so we do nothing!
                            if rfx_origin is None:
                                await self._transmit_physical(idx, new_state)

    async def _transmit_physical(self, idx: int, state: str) -> None:
        """Constructs a high-level PyRFXtrx payload and blasts it synchronously out the USB port."""
        config = self._outbound_map.get(idx)
        if not config:
            return

        target_hex = config["ON"] if state == "ON" else config["OFF"]
        protocol = config["protocol"]

        try:
            # ⚡ HIGH LEVEL PACKET CONSTRUCTION
            # Dynamically instantiate the exact protocol class requested in config.yaml (e.g. lowlevel.Lighting4)
            pkt_class = getattr(lowlevel, protocol, None)
            if not pkt_class:
                await self.logger.error(f"[Native RFX] Unknown protocol '{protocol}' requested for IDX {idx}")
                return

            pkt = pkt_class()

            # The Lighting4/PT2262 protocol embeds the command directly into the hex ID!
            if hasattr(pkt, 'parse_id'):
                # Handle library quirks: some older pyRFXtrx versions expect integers instead of hex strings
                try:
                    pkt.parse_id(target_hex)
                except (TypeError, ValueError):
                    pkt.parse_id(int(target_hex, 16))

            # ⚡ TRANSMIT
            # Because serial writes are highly isolated operations, running this inside
            # run_in_executor ensures it never blocks WanOS even if the USB driver momentarily hangs.
            if self.core and self.core.transport:
                await self.loop.run_in_executor(None, self.core.transport.send, pkt.data)
                await self.logger.info(
                    f"[Native RFX] Transmission Blasted: Virtual IDX {idx} -> Protocol: {protocol} | ID: {target_hex}")

        except Exception as e:
            await self.logger.error(f"[Native RFX] Failed to transmit payload for IDX {idx}: {e}")