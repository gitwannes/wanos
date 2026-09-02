# --- file: _lcd-agent/lcd_pi_agent.py ---
# LCD Pi Agent: subscribes to WanOS MQTT topics and renders WISC-compatible
# 16x2 HD44780 LCD text over I2C (PCF8574 backpack).
#
# Screen wiring:
# - screen 1 (sauna): I2C addr 0x27
# - screen 2 (control): I2C addr 0x26
#
# MQTT topics (default):
# - wanos/lcd/screen1 {line1,line2}
# - wanos/lcd/screen2 {line1,line2}
#
# Env configuration (from /home/wannes/wanos/.env — same path as WanOS main; never git):
# - WANOS_LCD_MQTT_BROKER_HOST
# - WANOS_LCD_MQTT_BROKER_PORT (default 1883)
# - WANOS_LCD_MQTT_USERNAME
# - WANOS_LCD_MQTT_PASSWORD
# - WANOS_LCD_SCREENSAVER_TIMEOUT_SECS (default 600)
#
# systemd EnvironmentFile loads .env; dotenv also loads it for manual runs.
# App log (sync Job 3 / wanoslcdlog choice 2): /var/log/wanos/wanos.log
# Console (journalctl / wanoslcdlog choice 1) is not copied by wanos-sync.
# Screen writes are logged at DEBUG into the same app log file.

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from aiomqtt import Client
from dotenv import load_dotenv
from smbus2 import SMBus

# Common PCF8574 backpack bit mapping used by many HD44780 I2C adapters:
# P0=RS, P2=EN, P3=Backlight, P4..P7=D4..D7.
RS_BIT = 0x01
EN_BIT = 0x04
BACKLIGHT_BIT = 0x08
NO_BACKLIGHT_BIT = 0x00

CUSTOM_CHARS = [
    # Char 0: heart
    [0x00, 0x00, 0x0A, 0x1F, 0x1F, 0x0E, 0x04, 0x00],
    # Char 1: degree
    [0x18, 0x16, 0x09, 0x08, 0x08, 0x09, 0x06, 0x00],
]

LOG = logging.getLogger("wanos.lcd")


def _setup_app_logging() -> None:
    """Write DEBUG+ lines to /var/log/wanos/wanos.log (same path family as WanOS)."""
    log_dir = "/var/log/wanos"
    log_path = os.path.join(log_dir, "wanos.log")
    try:
        os.makedirs(log_dir, exist_ok=True)
        handler: logging.Handler = logging.FileHandler(log_path, encoding="utf-8")
    except OSError:
        handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    # DEBUG so screen write lines land in wanos.log; INFO+ for lifecycle still appear.
    root.setLevel(logging.DEBUG)


def _visible_cell_len(s: str) -> int:
    """Counts LCD cells: '§X' counts as 1 cell; everything else counts as 1."""
    if not s:
        return 0
    n = 0
    i = 0
    while i < len(s):
        if s[i] == "§" and i + 1 < len(s) and s[i + 1].isdigit():
            n += 1
            i += 2
        else:
            n += 1
            i += 1
    return n


def _pad_to_16(s: str) -> str:
    """Pad a WISC escape string to 16 visible LCD cells."""
    s = s or ""
    cells = _visible_cell_len(s)
    if cells >= 16:
        return s
    return s + (" " * (16 - cells))


def _lcd_pretty_line_for_log(raw: str) -> str:
    """Map wire-format LCD escapes to readable log text (L3); MQTT payload unchanged."""
    s = str(raw or "")
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "§" and i + 1 < len(s) and s[i + 1].isdigit():
            slot = s[i + 1]
            if slot == "1":
                out.append("°C")
            elif slot == "0":
                out.append("♥")
            i += 2
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _lcd_semantic_line1(line1: str) -> str:
    """Collapse mm:ss countdown so DEBUG logs skip timer-only ticks (C34)."""
    return re.sub(r"\d{2}:\d{2}", "__:__", line1 or "")


def _lcd_semantic_key(line1: str, line2: str) -> tuple[str, str]:
    return (_lcd_semantic_line1(line1), line2 or "")


class Hd44780I2c:
    def __init__(self, *, bus_no: int, i2c_addr: int) -> None:
        self._bus = SMBus(bus_no)
        self._addr = i2c_addr
        self._backlight_on = True
        self._init_lcd()

    def _write_raw(self, value: int) -> None:
        self._bus.write_byte(self._addr, value & 0xFF)

    def _pulse_en(self, data: int) -> None:
        self._write_raw(data | EN_BIT)
        time.sleep(0.0005)
        self._write_raw(data & ~EN_BIT)
        time.sleep(0.0001)

    def _write_4bits(self, nibble_aligned: int) -> None:
        bl = BACKLIGHT_BIT if self._backlight_on else NO_BACKLIGHT_BIT
        self._write_raw(nibble_aligned | bl)
        self._pulse_en(nibble_aligned | bl)

    def _command(self, cmd: int) -> None:
        mode = 0x00
        self._write_4bits(mode | (cmd & 0xF0))
        self._write_4bits(mode | ((cmd << 4) & 0xF0))
        time.sleep(0.0001)

    def _data(self, data: int) -> None:
        mode = RS_BIT
        self._write_4bits(mode | (data & 0xF0))
        self._write_4bits(mode | ((data << 4) & 0xF0))
        time.sleep(0.0001)

    def _init_lcd(self) -> None:
        time.sleep(0.05)
        self._backlight_on = True
        self._write_4bits(0x30)
        time.sleep(0.005)
        self._write_4bits(0x30)
        time.sleep(0.001)
        self._write_4bits(0x30)
        time.sleep(0.001)
        self._write_4bits(0x20)
        time.sleep(0.001)
        self._command(0x28)
        self._command(0x0C)
        self._command(0x01)
        time.sleep(0.002)
        self._command(0x06)
        self._load_custom_chars()

    def _load_custom_chars(self) -> None:
        self._command(0x40)
        for char_bitmap in CUSTOM_CHARS:
            for b in char_bitmap:
                self._data(b)

    def backlight(self, on: bool) -> None:
        self._backlight_on = bool(on)
        self._write_raw(BACKLIGHT_BIT if self._backlight_on else NO_BACKLIGHT_BIT)

    def clear(self) -> None:
        self._command(0x01)
        time.sleep(0.002)

    def set_cursor(self, line_no: int, col: int = 0) -> None:
        base = 0x80 if line_no == 1 else 0xC0
        self._command(base + max(0, min(15, col)))

    def write_string(self, line_no: int, s: str) -> None:
        s = _pad_to_16(s)
        self.set_cursor(line_no, 0)
        i = 0
        while i < len(s):
            ch = s[i]
            if ch == "§" and i + 1 < len(s) and s[i + 1].isdigit():
                self._data(int(s[i + 1]))
                i += 2
                continue
            if ch == "°":
                self._data(0b11011111)
            else:
                self._data(ord(ch))
            i += 1


class TwoScreenRenderer:
    def __init__(self, *, bus_no: int, addr_screen1: int, addr_screen2: int) -> None:
        self.screen1 = Hd44780I2c(bus_no=bus_no, i2c_addr=addr_screen1)
        self.screen2 = Hd44780I2c(bus_no=bus_no, i2c_addr=addr_screen2)
        # Local blank flags — avoid re-clear / backlight churn / DEBUG spam when
        # screensaver (or MQTT blank) fires again while already blank.
        self._blank: dict[int, bool] = {1: False, 2: False}
        # Last semantic content logged per screen (skip countdown-only MQTT ticks).
        self._last_logged_key: dict[int, tuple[str, str]] = {}

    def blank_screen(self, screen: int) -> None:
        if self._blank.get(screen):
            return
        lcd = self.screen1 if screen == 1 else self.screen2
        lcd.clear()
        lcd.backlight(False)
        self._blank[screen] = True
        self._last_logged_key.pop(screen, None)
        LOG.debug("LCD screen%d blank", screen)

    def print_screen(self, *, screen: int, line1: str, line2: str) -> None:
        lcd = self.screen1 if screen == 1 else self.screen2
        if (line1 or "").strip() or (line2 or "").strip():
            lcd.backlight(True)
        else:
            lcd.backlight(False)
        lcd.write_string(1, line1 or "")
        lcd.write_string(2, line2 or "")
        self._blank[screen] = False
        sem_key = _lcd_semantic_key(line1 or "", line2 or "")
        if self._last_logged_key.get(screen) == sem_key:
            return
        self._last_logged_key[screen] = sem_key
        LOG.debug(
            "LCD screen%d | L1=%r | L2=%r",
            screen,
            _lcd_pretty_line_for_log(line1 or ""),
            _lcd_pretty_line_for_log(line2 or ""),
        )


@dataclass
class Topics:
    screen1: str
    screen2: str


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


def _env_str(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v if v is not None else default


async def main() -> None:
    # Same path convention as WanOS main; systemd EnvironmentFile also points here.
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.is_file():
        load_dotenv(dotenv_path=env_path)

    _setup_app_logging()

    broker_host = _env_str("WANOS_LCD_MQTT_BROKER_HOST")
    if not broker_host:
        raise SystemExit("Missing WANOS_LCD_MQTT_BROKER_HOST")

    topics = Topics(
        screen1=_env_str("WANOS_LCD_TOPIC_SCREEN1", "wanos/lcd/screen1"),
        screen2=_env_str("WANOS_LCD_TOPIC_SCREEN2", "wanos/lcd/screen2"),
    )

    mqtt_port = _env_int("WANOS_LCD_MQTT_BROKER_PORT", 1883)
    mqtt_user = _env_str("WANOS_LCD_MQTT_USERNAME", "st")
    mqtt_pass = _env_str("WANOS_LCD_MQTT_PASSWORD")
    if not mqtt_pass:
        raise SystemExit("Missing WANOS_LCD_MQTT_PASSWORD")

    bus_no = _env_int("WANOS_LCD_I2C_BUS", 1)
    addr_screen1 = _env_int("WANOS_LCD_ADDR_SCREEN1", 0x27)
    addr_screen2 = _env_int("WANOS_LCD_ADDR_SCREEN2", 0x26)
    ss_timeout = _env_int("WANOS_LCD_SCREENSAVER_TIMEOUT_SECS", 600)

    LOG.info(
        "LCD agent starting (broker=%s:%s screen1=0x%02x screen2=0x%02x)",
        broker_host,
        mqtt_port,
        addr_screen1,
        addr_screen2,
    )

    renderer = TwoScreenRenderer(
        bus_no=bus_no, addr_screen1=addr_screen1, addr_screen2=addr_screen2
    )
    renderer.blank_screen(1)
    renderer.blank_screen(2)

    last_activity_unix = int(time.time())

    async def _handle(topic: str, payload: bytes) -> None:
        nonlocal last_activity_unix
        last_activity_unix = int(time.time())
        try:
            msg = json.loads(payload.decode("utf-8"))
        except Exception:
            LOG.warning("Bad LCD payload on %s", topic)
            return

        line1 = str(msg.get("line1") or "")
        line2 = str(msg.get("line2") or "")
        topic_s = str(topic)
        # WanOS blank signal = both lines empty → clear + backlight off.
        is_blank = not line1.strip() and not line2.strip()
        if topic_s == topics.screen1:
            if is_blank:
                renderer.blank_screen(1)
            else:
                renderer.print_screen(screen=1, line1=line1, line2=line2)
        elif topic_s == topics.screen2:
            if is_blank:
                renderer.blank_screen(2)
            else:
                renderer.print_screen(screen=2, line1=line1, line2=line2)

    async def _screensaver_loop() -> None:
        nonlocal last_activity_unix
        while True:
            await asyncio.sleep(1.0)
            now = int(time.time())
            if now - last_activity_unix > ss_timeout:
                renderer.blank_screen(2)
                last_activity_unix = now

    async with Client(
        broker_host,
        port=mqtt_port,
        username=mqtt_user,
        password=mqtt_pass,
    ) as client:
        await client.subscribe(topics.screen1)
        await client.subscribe(topics.screen2)
        LOG.info("Subscribed to %s and %s", topics.screen1, topics.screen2)
        asyncio.create_task(_screensaver_loop())
        # aiomqtt ≥2.0: single client-wide queue via client.messages
        # (unfiltered_messages was removed).
        async for m in client.messages:
            await _handle(str(m.topic), m.payload)


if __name__ == "__main__":
    asyncio.run(main())
