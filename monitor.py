# --- file: monitor.py ---
import asyncio
import json
import os
import yaml
from dotenv import load_dotenv
import aiomqtt
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, RichLog, Static


# 1. Load Configurations exactly like the main app
def load_mqtt_configs():
    load_dotenv()
    with open("hardware.yaml", "r") as f:
        hw = yaml.safe_load(f)

    # ⚡ FIXED: Extract valid IDXs dynamically from the hardware config
    valid_idxs = []
    for name, config in hw.get("domoticz", {}).get("idx", {}).items():
        if "id" in config:
            valid_idxs.append(config["id"])

    return {
        "wanos": {
            "host": hw["wanos"]["mqtt"]["broker_host"],
            "port": hw["wanos"]["mqtt"].get("port", 1883),
            "user": hw["wanos"]["mqtt"].get("username"),
            "pass": os.getenv("WANOS_MQTT_PASSWORD")
        },
        "domoticz": {
            "host": hw["domoticz"]["mqtt"]["broker_host"],
            "port": hw["domoticz"]["mqtt"].get("port", 1883),
            "user": hw["domoticz"]["mqtt"].get("username"),
            "pass": os.getenv("DOM_MQTT_PASSWORD"),
            "valid_idxs": valid_idxs  # Pass the approved list down to the listener
        }
    }


class LogMonitorApp(App):
    """A hacker-style split-screen terminal for WanOS & Domoticz telemetry."""

    # CSS styling for the terminal blocks
    CSS = """
    RichLog {
        border: solid green;
        height: 100%;
        background: #0a0a0a;
    }
    #domoticz-log {
        border: solid cyan;
    }
    .title {
        text-align: center;
        background: #111;
        color: white;
        padding: 1;
        text-style: bold;
    }
    """

    # Global Terminal Keybinds
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("p", "toggle_pause", "Pause/Resume Stream"),
        ("c", "clear_logs", "Clear Screens")
    ]

    def __init__(self):
        super().__init__()
        self.paused = False
        self.tasks = []

    def compose(self) -> ComposeResult:
        """Constructs the split-screen UI."""
        yield Header(show_clock=True)
        with Horizontal():
            # Left Screen: WanOS Automation Engine
            with Vertical():
                yield Static("🤖 AUTOMATION ENGINE (WanOS)", classes="title")
                yield RichLog(id="wanos-log", markup=True, highlight=True, wrap=True)
            # Right Screen: Domoticz Hardware Firehose
            with Vertical():
                yield Static("🔌 DOMOTICZ FIREHOSE", classes="title")
                yield RichLog(id="domoticz-log", markup=True, highlight=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        """Runs automatically when the TUI boots."""
        configs = load_mqtt_configs()

        # We launch two separate MQTT clients so we can listen to both brokers simultaneously!
        self.tasks.append(asyncio.create_task(self.listen_wanos(configs["wanos"])))
        self.tasks.append(asyncio.create_task(self.listen_domoticz(configs["domoticz"])))

    def action_toggle_pause(self) -> None:
        """Handles the 'P' key press."""
        self.paused = not self.paused
        status = "PAUSED" if self.paused else "RESUMED"
        color = "yellow" if self.paused else "green"
        self.query_one("#wanos-log", RichLog).write(f"[bold {color}]--- STREAM {status} ---[/]")
        self.query_one("#domoticz-log", RichLog).write(f"[bold {color}]--- STREAM {status} ---[/]")

    def action_clear_logs(self) -> None:
        """Handles the 'C' key press."""
        self.query_one("#wanos-log", RichLog).clear()
        self.query_one("#domoticz-log", RichLog).clear()

    async def listen_wanos(self, cfg):
        """Dedicated background task to fetch WanOS events."""
        log_widget = self.query_one("#wanos-log", RichLog)
        try:
            async with aiomqtt.Client(hostname=cfg["host"], port=cfg["port"], username=cfg["user"],
                                      password=cfg["pass"]) as client:
                log_widget.write(f"[bold green]✅ Connected to Local Broker ({cfg['host']})[/]")

                # Listen to both Status and Debug streams
                await client.subscribe("wanos/console/#")

                async for message in client.messages:
                    if self.paused: continue
                    payload = message.payload.decode('utf-8')
                    try:
                        data = json.loads(payload)
                        level = data.get("level", "INFO")
                        msg = data.get("message", payload)
                        ts = data.get("timestamp", "").split(" ")[-1]  # Just grab the HH:MM:SS

                        # Color coding based on WanosLogger levels
                        color = "white"
                        if level == "DEBUG":
                            color = "grey50"
                        elif level == "SUCCESS":
                            color = "green"
                        elif level == "WARNING":
                            color = "yellow"
                        elif level == "ERROR":
                            color = "red"
                        elif level == "INFO":
                            color = "cyan"

                        log_widget.write(f"[[blue]{ts}[/]] [[bold {color}]{level}[/]] {msg}")
                    except:
                        log_widget.write(f"[grey50]{payload}[/]")
        except Exception as e:
            log_widget.write(f"[bold red]❌ WanOS MQTT Connection Failed: {e}[/]")

    async def listen_domoticz(self, cfg):
        """Dedicated background task to fetch Domoticz hardware events."""
        log_widget = self.query_one("#domoticz-log", RichLog)
        try:
            async with aiomqtt.Client(hostname=cfg["host"], port=cfg["port"], username=cfg["user"],
                                      password=cfg["pass"]) as client:
                log_widget.write(f"[bold cyan]✅ Connected to Remote Domoticz Broker ({cfg['host']})[/]")

                # We listen directly to the raw network out topic
                await client.subscribe("domoticz/out")

                async for message in client.messages:
                    if self.paused: continue
                    payload = message.payload.decode('utf-8')
                    try:
                        data = json.loads(payload)
                        idx = data.get("idx")

                        # ⚡ FIXED: Silently drop any IDX not explicitly declared in hardware.yaml
                        if idx not in cfg.get("valid_idxs", []):
                            continue

                        nvalue = data.get("nvalue", "-")
                        svalue = data.get("svalue1", "") or data.get("svalue", "")

                        # Cleanly format the data block
                        log_widget.write(
                            f"[[cyan]IDX {idx}[/]] nval: [bold white]{nvalue}[/], sval: [white]{svalue}[/]")
                        log_widget.write(f"[grey50]{payload}[/]\n")  # Print raw JSON directly below it
                    except:
                        # Safely ignore unparseable payloads to keep the terminal perfectly clean
                        pass
        except Exception as e:
            log_widget.write(f"[bold red]❌ Domoticz MQTT Connection Failed: {e}[/]")


if __name__ == "__main__":
    app = LogMonitorApp()
    app.run()