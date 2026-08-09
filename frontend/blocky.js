// Phase 6B: unified Blockly canvas for schema v2 (trigger + ordered cases).
// Contextual dropdowns: only show entries valid for the current trigger / device type.
// Phase 6C: rich action authoring — Hue preset XOR custom color (iro→bri/xy), blinds open %, Sonos/Onkyo volume, Sonos station.
// Phase B10A: editor trust — Hue picker-only / type-switch rebuild / no restore-modal;
//   toolbar Delete (no trashcan); Blockly Events disable/enable paired (v13 refcount); dirty from canvas.

/** Min viewport width for History / Automation and the top-row join (tablets+). */
const WANOS_WIDE_MIN_PX = 768;

/** History & Automation: bounce phones to Device Explorer (also on shrink).
 *  Returns true when the viewport is too narrow (caller should abort init). */
function wanosRedirectIfNarrow() {
    const mq = window.matchMedia(`(min-width: ${WANOS_WIDE_MIN_PX}px)`);
    const bounce = () => {
        if (!mq.matches) window.location.replace("/deviceexplorer.html");
    };
    bounce();
    if (typeof mq.addEventListener === "function") mq.addEventListener("change", bounce);
    else if (typeof mq.addListener === "function") mq.addListener(bounce);
    return !mq.matches;
}

/** Keep in sync with core/schedule_events.SCHEDULE_WINDOW_EDGES (enter, exit). */
const BLOCKY_SCHEDULE_WINDOW_EDGES = {
    blinds: ["BLINDS_OPEN_TRIGGER", "BLINDS_CLOSE_TRIGGER"],
    twilight_evening: ["SUNSET_TRIGGER", "EVENING_OFF_TRIGGER"],
    twilight_morning: ["MORNING_ON_TRIGGER", "SUNRISE_TRIGGER"],
    sauna: ["SAUNA_ON", "SAUNA_OFF"],
    ir: ["IR_ON", "IR_OFF"],
    cinema: ["SCENE_CINEMA_ON", "SCENE_CINEMA_OFF"]
};

/** Display labels for concrete events (dropdowns + schedule hints). Stored values stay canonical. */
const BLOCKY_EVENT_LABELS = {
    BLINDS_OPEN_TRIGGER: "Blinds open",
    BLINDS_CLOSE_TRIGGER: "Blinds close",
    MORNING_ON_TRIGGER: "Morning on",
    SUNRISE_TRIGGER: "Sunrise",
    SUNSET_TRIGGER: "Sunset",
    EVENING_OFF_TRIGGER: "Evening off",
    SAUNA_ON: "Sauna on",
    SAUNA_OFF: "Sauna off",
    IR_ON: "IR on",
    IR_OFF: "IR off",
    SCENE_CINEMA_ON: "Cinema on",
    SCENE_CINEMA_OFF: "Cinema off",
    SCENE_ALL_OFF: "All off",
    SCENE_GOCOSY: "Go cosy",
    SCENE_GV_OFF: "Ground floor off",
    SCENE_VERDIEP1_OFF: "Floor 1 off",
    SCENE_VERDIEP2_OFF: "Floor 2 off",
    TWILIGHT_MORNING_ON_TRIGGER: "Morning on",
    TWILIGHT_MORNING_OFF_TRIGGER: "Sunrise",
    TWILIGHT_EVENING_ON_TRIGGER: "Sunset",
    TWILIGHT_EVENING_OFF_TRIGGER: "Evening off"
};

const BLOCKY_EDGE_STATES = [
    ["ON", "ON"], ["OFF", "OFF"]
];

const BLOCKY_ROOT_TRIGGERS = new Set([
    "b_trig_device", "b_trig_or", "b_trig_event", "b_trig_family"
]);

/** Sensor / temp-class — excluded from pickers (motion is separate: trigger OK, never action). */
const BLOCKY_SENSOR_LIKE_TYPES = new Set([
    "sensor", "temp_hum", "temp", "hum", "power", "energy", "fluid"
]);

/** Types that can appear as action targets. */
const BLOCKY_ACTUATOR_TYPES = new Set([
    "switch", "light", "blinds", "shutter", "speaker", "media_player"
]);

function blockyEventLabel(ev) {
    const key = String(ev || "");
    if (BLOCKY_EVENT_LABELS[key]) return BLOCKY_EVENT_LABELS[key];
    const pretty = key.replace(/_TRIGGER$/i, "").replace(/_/g, " ").toLowerCase()
        .replace(/\b\w/g, (c) => c.toUpperCase());
    return pretty || key;
}

function blockyEdgeShort(ev) {
    return blockyEventLabel(ev);
}

function blockyScheduleWindowHint(fam) {
    const edges = BLOCKY_SCHEDULE_WINDOW_EDGES[fam];
    if (!edges) return "";
    const a = blockyEdgeShort(edges[0]);
    const b = blockyEdgeShort(edges[1]);
    if (fam === "blinds") {
        return `Fires twice: ${a} (clamped), then ${b} (clamped). Not raw sunrise/sunset.`;
    }
    if (fam === "twilight_morning" || fam === "twilight_evening") {
        return `Fires twice: at ${a}, then at ${b}. Not blinds open/close.`;
    }
    if (fam === "sauna" || fam === "ir" || fam === "cinema") {
        return `Fires on either edge: ${a} or ${b}. Not a clock schedule.`;
    }
    return `Fires twice: ${a}, then ${b}.`;
}

function blockyEntityMeta(eid) {
    const app = BlockyRT.app;
    if (app && Array.isArray(app.entityOptions)) {
        return app.entityOptions.find((o) => o.eid === eid) || null;
    }
    return null;
}

function blockyEntityTypeOf(eid) {
    const opt = blockyEntityMeta(eid);
    if (opt && opt.type) return String(opt.type).toLowerCase();
    const e = String(eid || "");
    if (e.startsWith("blinds.")) return "blinds";
    if (e.startsWith("hue.")) return "light";
    if (e.startsWith("media_player.")) return "speaker";
    if (e.startsWith("sensor.door.") || e.startsWith("door.")) return "door";
    if (e.includes("motion")) return "motion";
    if (e.startsWith("sensor.")) return "sensor";
    if (e.startsWith("switch.")) return "switch";
    return "";
}

function blockyEntityOriginOf(eid) {
    const opt = blockyEntityMeta(eid);
    return opt && opt.origin ? String(opt.origin).toLowerCase() : "";
}

function blockyIsMotionEntity(optOrEid) {
    const type = String(
        (optOrEid && typeof optOrEid === "object" ? optOrEid.type : null)
        || blockyEntityTypeOf(typeof optOrEid === "string" ? optOrEid : (optOrEid && optOrEid.eid))
        || ""
    ).toLowerCase();
    if (type === "motion") return true;
    const eid = String(
        (optOrEid && typeof optOrEid === "object" ? optOrEid.eid : optOrEid) || ""
    );
    const name = (optOrEid && typeof optOrEid === "object" ? optOrEid.name : "") || "";
    return /motion/i.test(eid) || /motion/i.test(name);
}

function blockyIsSensorLikeEntity(optOrEid, typeHint) {
    if (blockyIsMotionEntity(optOrEid)) return false; // motion ≠ temp/power class
    const type = String(
        (optOrEid && typeof optOrEid === "object" ? optOrEid.type : typeHint)
        || blockyEntityTypeOf(typeof optOrEid === "string" ? optOrEid : (optOrEid && optOrEid.eid))
        || ""
    ).toLowerCase();
    if (BLOCKY_SENSOR_LIKE_TYPES.has(type)) return true;
    const eid = String(
        (optOrEid && typeof optOrEid === "object" ? optOrEid.eid : optOrEid) || ""
    );
    if (eid.startsWith("sensor.door.")) return false;
    if (eid.startsWith("sensor.")) return true;
    return false;
}

function blockyIsActuatorEntity(optOrEid) {
    const type = String(
        (optOrEid && typeof optOrEid === "object" ? optOrEid.type : null)
        || blockyEntityTypeOf(typeof optOrEid === "string" ? optOrEid : (optOrEid && optOrEid.eid))
        || ""
    ).toLowerCase();
    if (BLOCKY_ACTUATOR_TYPES.has(type)) return true;
    const eid = String(
        (optOrEid && typeof optOrEid === "object" ? optOrEid.eid : optOrEid) || ""
    );
    return (
        eid.startsWith("switch.")
        || eid.startsWith("hue.")
        || eid.startsWith("blinds.")
        || eid.startsWith("media_player.")
    );
}

function blockyEntityAllowedForRole(opt, role) {
    if (role === "action") {
        // Motion / sensors / doors cannot be actioned.
        return blockyIsActuatorEntity(opt) && !blockyIsMotionEntity(opt);
    }
    if (blockyIsMotionEntity(opt)) {
        // Motion OK as When-device trigger (garage/toilet); not as condition for now.
        return role === "trigger";
    }
    return !blockyIsSensorLikeEntity(opt);
}

function blockyCaseMatchOptions(caseBlock) {
    let opts;
    try {
        const root = caseBlock.getRootBlock && caseBlock.getRootBlock();
        if (root && root.type === "b_trig_family") {
            const fam = root.getFieldValue("FAMILY");
            const edges = BLOCKY_SCHEDULE_WINDOW_EDGES[fam];
            if (edges) {
                opts = [
                    [`at start (${blockyEdgeShort(edges[0])})`, "ON"],
                    [`at end (${blockyEdgeShort(edges[1])})`, "OFF"]
                ];
            }
        } else if (root && root.type === "b_trig_device") {
            const type = blockyEntityTypeOf(root.getFieldValue("ENTITY"));
            if (type === "blinds" || type === "shutter") {
                opts = [
                    ["when OPEN", "OPEN"],
                    ["when CLOSED", "CLOSED"]
                ];
            } else {
                opts = [
                    ["when ON", "ON"],
                    ["when OFF", "OFF"]
                ];
            }
        } else if (root && root.type === "b_trig_or") {
            opts = [["(conditions only)", "NONE"]];
        } else if (root && root.type === "b_trig_event") {
            opts = [["(run if conditions)", "NONE"]];
        }
    } catch (e) { /* ignore */ }
    if (!opts) {
        opts = [
            ["when ON", "ON"],
            ["when OFF", "OFF"]
        ];
    }
    return opts;
}

function blockyEdgeStateOptions(block) {
    const type = blockyEntityTypeOf(block.getFieldValue("ENTITY"));
    if (type === "blinds" || type === "shutter") {
        return [["OPEN", "OPEN"], ["CLOSED", "CLOSED"]];
    }
    return BLOCKY_EDGE_STATES.slice();
}

/**
 * Action state entries by device type / origin.
 * RFX / Sonos / Onkyo / Epson: no FORCE_* (engine always-forces RFX; OFF-only for the AV trio).
 * Blinds: STATE is a placeholder; position lives in OPEN_PCT (operator open %).
 */
function blockyActionStateOptions(block) {
    const eid = block.getFieldValue("ENTITY");
    const type = blockyEntityTypeOf(eid);
    const origin = String(blockyEntityOriginOf(eid) || "").toLowerCase();
    if (type === "blinds" || type === "shutter") {
        return [["OPEN", "OPEN"], ["CLOSED", "CLOSED"], ["position %", "POS"]];
    }
    if (type === "light" || type === "hue") {
        return [["ON", "ON"], ["OFF", "OFF"]];
    }
    if (type === "speaker" || type === "media_player") {
        return [["ON", "ON"], ["OFF", "OFF"]];
    }
    // RFX + Epson: always-forced at engine — no FORCE_* in the menu.
    if (origin === "rfxcom" || origin === "epson") {
        return [["ON", "ON"], ["OFF", "OFF"]];
    }
    // Z-Wave / generic switches — explicit FORCE remains available.
    return [
        ["ON", "ON"], ["OFF", "OFF"],
        ["FORCE_ON", "FORCE_ON"], ["FORCE_OFF", "FORCE_OFF"]
    ];
}

function blockyConditionStateOptions(block) {
    const type = blockyEntityTypeOf(block.getFieldValue("ENTITY"));
    if (type === "blinds" || type === "shutter") {
        return [["Open", "0"], ["Closed", "100"]];
    }
    if (type === "door") {
        return [["OPEN", "OPEN"], ["CLOSED", "CLOSED"]];
    }
    return [["ON", "ON"], ["OFF", "OFF"]];
}

/** Stored blinds state = closed % (0 open … 100 closed). UI = open %. */
function blockyOpenPctFromStored(stored) {
    const n = Number(stored);
    if (!Number.isFinite(n)) return 100;
    return Math.max(0, Math.min(100, 100 - n));
}

function blockyStoredFromOpenPct(openPct) {
    const n = Number(openPct);
    if (!Number.isFinite(n)) return "0";
    return String(Math.max(0, Math.min(100, Math.round(100 - n))));
}

/** Map stored blinds closed-% (or OPEN/CLOSED) → Blockly STATE value. */
function blockyBlindsUiStateFromStored(stored) {
    if (stored === "OPEN" || stored === "CLOSED" || stored === "POS") return stored;
    const n = Number(stored);
    if (n === 0) return "OPEN";
    if (n === 100) return "CLOSED";
    if (Number.isFinite(n)) return "POS";
    return "OPEN";
}

function blockyHuePresetsMap() {
    const app = BlockyRT.app;
    if (app && app.huePresets && typeof app.huePresets === "object") return app.huePresets;
    if (app && app.state && app.state.system && app.state.system.hue_presets) {
        return app.state.system.hue_presets;
    }
    return {};
}

function blockySonosStationsMap() {
    const app = BlockyRT.app;
    if (app && app.sonosStations && typeof app.sonosStations === "object") return app.sonosStations;
    if (app && app.state && app.state.system && app.state.system.sonos_stations) {
        return app.state.system.sonos_stations;
    }
    return {};
}

function blockyHuePresetOptions(stickyKey) {
    const presets = blockyHuePresetsMap();
    const keys = Object.keys(presets);
    const opts = [];
    const seen = new Set();
    keys.forEach((k) => {
        const p = presets[k];
        const label = (p && p.name) ? String(p.name) : k;
        opts.push([label, k]);
        seen.add(k);
    });
    blockyStickyRichKeys("preset", stickyKey).forEach((k) => {
        if (!seen.has(k)) {
            const label = keys.length ? `${k} · (missing)` : k;
            opts.push([label, k]);
            seen.add(k);
        }
    });
    // Never offer empty "(none)" — preset mode always needs a real key.
    return opts.length ? opts : [["(no presets in config)", ""]];
}

/** Station keys from config + sticky (open rule / pending load) so setValue cannot be rejected. */
function blockySonosStationOptions(stickyKey) {
    const stations = blockySonosStationsMap();
    const known = Object.keys(stations);
    const opts = [["(none)", ""]];
    const seen = new Set([""]);
    known.forEach((k) => {
        opts.push([k, k]);
        seen.add(k);
    });
    blockyStickyRichKeys("station", stickyKey).forEach((k) => {
        if (!seen.has(k)) {
            const label = known.length ? `${k} · (missing from config)` : k;
            opts.push([label, k]);
            seen.add(k);
        }
    });
    return opts;
}

/** Collect preset/station keys from open ruleJson, pending apply, and workspace fields. */
function blockyStickyRichKeys(kind, stickyKey) {
    const out = new Set();
    if (stickyKey) out.add(String(stickyKey));
    const app = BlockyRT.app;
    if (app && app._pendingRichSticky && app._pendingRichSticky[kind]) {
        app._pendingRichSticky[kind].forEach((k) => out.add(String(k)));
    }
    try {
        const rule = JSON.parse((app && app.editor && app.editor.ruleJson) || "{}");
        (rule.cases || []).forEach((c) => {
            (c.actions || []).forEach((a) => {
                if (kind === "station" && a.station) out.add(String(a.station));
                if (kind === "preset" && a.preset) out.add(String(a.preset));
            });
        });
    } catch (e) { /* ignore */ }
    try {
        const ws = blockyWs();
        const field = kind === "station" ? "STATION" : "PRESET";
        if (ws) {
            ws.getAllBlocks(false).forEach((b) => {
                if (b.type !== "b_action_device" || !b.getField(field)) return;
                const v = b.getFieldValue(field);
                if (v) out.add(String(v));
            });
        }
    } catch (e) { /* ignore */ }
    return [...out].filter(Boolean);
}

function blockyEntityMaxVolume(eid) {
    const opt = blockyEntityMeta(eid);
    if (opt && opt.max_volume != null) {
        const n = Number(opt.max_volume);
        if (Number.isFinite(n) && n > 0) return n;
    }
    const origin = String(blockyEntityOriginOf(eid) || "").toLowerCase();
    if (origin === "onkyo") return 60;
    if (origin === "sonos") return 70;
    return 100;
}

function blockySafeSetField(block, name, value) {
    if (!block || value == null) return;
    try {
        const f = block.getField(name);
        if (!f) return;
        f.setValue(value);
    } catch (e) { /* ignore */ }
}

/** CIE xy + bri → hex (same math as Device Explorer). */
function blockyXyToHex(x, y, bri) {
    if (x === undefined || y === undefined || x == null || y == null) return "#FFD180";
    let z = 1.0 - x - y;
    const Y = (bri !== undefined && bri != null ? bri : 100) / 100.0;
    if (!y) return "#FFD180";
    const X = (Y / y) * x;
    const Z = (Y / y) * z;
    let r = X * 1.656492 - Y * 0.354851 - Z * 0.255038;
    let g = -X * 0.707196 + Y * 1.655397 + Z * 0.036152;
    let b = X * 0.051713 - Y * 0.121364 + Z * 1.011530;
    r = r <= 0.0031308 ? 12.92 * r : (1.0 + 0.055) * Math.pow(r, (1.0 / 2.4)) - 0.055;
    g = g <= 0.0031308 ? 12.92 * g : (1.0 + 0.055) * Math.pow(g, (1.0 / 2.4)) - 0.055;
    b = b <= 0.0031308 ? 12.92 * b : (1.0 + 0.055) * Math.pow(b, (1.0 / 2.4)) - 0.055;
    r = Math.max(0, Math.min(1, r));
    g = Math.max(0, Math.min(1, g));
    b = Math.max(0, Math.min(1, b));
    const toHex = (c) => Math.round(c * 255).toString(16).padStart(2, "0");
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`.toUpperCase();
}

/** Hex → CIE xy (same math as Device Explorer). */
function blockyHexToXy(hex) {
    let h = String(hex || "").replace("#", "");
    if (h.length === 3) h = h.split("").map((c) => c + c).join("");
    if (h.length !== 6) return [0.4575, 0.4099];
    let r = parseInt(h.slice(0, 2), 16) / 255;
    let g = parseInt(h.slice(2, 4), 16) / 255;
    let b = parseInt(h.slice(4, 6), 16) / 255;
    r = r > 0.04045 ? Math.pow((r + 0.055) / 1.055, 2.4) : r / 12.92;
    g = g > 0.04045 ? Math.pow((g + 0.055) / 1.055, 2.4) : g / 12.92;
    b = b > 0.04045 ? Math.pow((b + 0.055) / 1.055, 2.4) : b / 12.92;
    const X = r * 0.664511 + g * 0.154324 + b * 0.162028;
    const Y = r * 0.283881 + g * 0.668433 + b * 0.047685;
    const Z = r * 0.000088 + g * 0.072310 + b * 0.986039;
    const sum = X + Y + Z;
    if (sum <= 0) return [0.4575, 0.4099];
    return [X / sum, Y / sum];
}

function blockyCloseHueColorModal() {
    // Drop any queued reopen from HUE_MODE validators.
    if (BlockyRT.pendingRichOpts) BlockyRT.pendingRichOpts.openWheel = false;
    const app = BlockyRT.app;
    if (app) app.blockyColorTargetId = null;
    const dlg = document.getElementById("blocky_hue_color_modal");
    if (dlg && typeof dlg.close === "function") {
        try { dlg.close(); } catch (e) { /* ignore */ }
    }
}

function blockyOpenHueColorModal(block) {
    const app = BlockyRT.app;
    if (!app || !block || block._hueSuppressWheel || block._richUpdating) return;
    if (BlockyRT.loading || BlockyRT.suppressHueWheel) return;
    app.blockyColorTargetId = block.id;
    app.blockyColorBri = block._hueBri != null ? Number(block._hueBri) : 100;
    app.blockyColorHex = block._hueHex || "#FFD180";
    const dlg = document.getElementById("blocky_hue_color_modal");
    if (!dlg) return;
    if (!dlg.open) dlg.showModal();
    queueMicrotask(() => {
        if (!window.iro || !dlg.open) return;
        const host = document.getElementById("blocky-color-picker-container");
        if (!host) return;
        if (!BlockyRT.colorPicker) {
            host.innerHTML = "";
            BlockyRT.colorPicker = new iro.ColorPicker(host, {
                width: 220,
                color: app.blockyColorHex,
                layout: [{ component: iro.ui.Wheel, options: {} }]
            });
            BlockyRT.colorPicker.on("color:change", (color) => {
                if (BlockyRT.app) BlockyRT.app.blockyColorHex = color.hexString;
            });
        } else {
            try { BlockyRT.colorPicker.color.hexString = app.blockyColorHex; } catch (e) { /* ignore */ }
        }
    });
}

function blockyApplyHueColorModal() {
    const app = BlockyRT.app;
    const ws = blockyWs();
    if (!app || !ws || !app.blockyColorTargetId) {
        blockyCloseHueColorModal();
        return;
    }
    const block = ws.getBlockById(app.blockyColorTargetId);
    if (!block) {
        blockyCloseHueColorModal();
        return;
    }
    const bri = Math.max(1, Math.min(100, Number(app.blockyColorBri) || 100));
    const hex = String(app.blockyColorHex || "#FFD180");
    const xy = blockyHexToXy(hex);
    block._hueBri = bri;
    block._hueXy = xy;
    block._hueHex = hex.toUpperCase();
    // Prevent HUE_MODE validators from reopening the wheel while we sync shape.
    block._hueSuppressWheel = true;
    try {
        blockyActionUpdateRichShape(block, { forceState: "ON", forceHueMode: "CUSTOM" });
        blockyPaintHueSwatch(block);
    } finally {
        block._hueSuppressWheel = false;
    }
    if (typeof app.markEditorDirty === "function") app.markEditorDirty();
    blockyCloseHueColorModal();
}

function blockyPaintHueSwatch(block) {
    const f = block && block.getField("COLOR_SWATCH");
    if (!f) return;
    const hex = block._hueHex || "#FFD180";
    try {
        const el = (typeof f.getTextElement === "function" ? f.getTextElement() : null)
            || f.textElement_;
        if (el) el.style.fill = hex;
    } catch (e) { /* ignore */ }
}

function blockyClearActionRichSticky(block) {
    if (!block) return;
    delete block._hueBri;
    delete block._hueXy;
    delete block._hueHex;
    delete block._pendingPreset;
    delete block._pendingStation;
    blockyRemoveInput(block, "RICH_BLINDS");
    blockyRemoveInput(block, "RICH_HUE_MODE");
    blockyRemoveInput(block, "RICH_HUE_PRESET");
    blockyRemoveInput(block, "RICH_HUE_CUSTOM");
    blockyRemoveInput(block, "RICH_AUDIO");
}

/** Remove a named dummy input if present (never throws). */
function blockyRemoveInput(block, name) {
    if (!block || !block.getInput(name)) return;
    try { block.removeInput(name); } catch (e) { /* ignore */ }
}

/**
 * Queue rich-shape sync after the current field commit finishes.
 * Independent of uniqueness timer so load/cancel cannot drop UI updates.
 */
function blockyQueueRichShape(block, opts) {
    if (!block || block.isInFlyout) return;
    opts = opts || {};
    BlockyRT.pendingRichOpts = Object.assign({}, BlockyRT.pendingRichOpts || {}, opts, {
        blockId: block.id
    });
    if (BlockyRT.richTimer) clearTimeout(BlockyRT.richTimer);
    BlockyRT.richTimer = setTimeout(() => {
        BlockyRT.richTimer = null;
        const pending = BlockyRT.pendingRichOpts;
        BlockyRT.pendingRichOpts = null;
        if (!pending || !pending.blockId) return;
        const ws = blockyWs();
        const blk = ws && ws.getBlockById(pending.blockId);
        if (!blk || blk.type !== "b_action_device") return;
        const openWheel = !!pending.openWheel;
        delete pending.openWheel;
        delete pending.blockId;
        blockyActionUpdateRichShape(blk, pending);
        if (openWheel && !BlockyRT.loading && !BlockyRT.suppressHueWheel) {
            blockyOpenHueColorModal(blk);
        }
    }, 0);
}

function blockyRemoveHueSwatchField(block) {
    if (!block || !block.getField("COLOR_SWATCH")) return;
    const input = block.getInput("RICH_HUE_MODE");
    if (!input) return;
    try { input.removeField("COLOR_SWATCH"); } catch (e) { /* ignore */ }
}

function blockyEnsureHueSwatchField(block) {
    if (!block || block.getField("COLOR_SWATCH")) return;
    const input = block.getInput("RICH_HUE_MODE");
    if (!input) return;
    try {
        input.appendField(new Blockly.FieldLabel("⬤"), "COLOR_SWATCH");
    } catch (e) { /* ignore */ }
}

/** Ensure Hue mode dropdown exists once — never dispose it while light is ON. */
function blockyEnsureHueModeInput(block) {
    if (block.getInput("RICH_HUE_MODE")) return;
    const modeOpts = [
        ["named preset", "PRESET"],
        ["custom color", "CUSTOM"],
        ["(no color)", "NONE"]
    ];
    block.appendDummyInput("RICH_HUE_MODE")
        .appendField("color")
        .appendField(new Blockly.FieldDropdown(modeOpts, (newMode) => {
            if (block._richUpdating || block._hueSuppressWheel || BlockyRT.loading || BlockyRT.suppressHueWheel) {
                return newMode;
            }
            // Validator runs before value commits — schedule shape after.
            if (newMode === "CUSTOM") {
                blockyQueueRichShape(block, {
                    forceState: "ON",
                    forceHueMode: "CUSTOM",
                    openWheel: true
                });
            } else {
                if (newMode !== "PRESET") block._pendingPreset = null;
                blockyQueueRichShape(block, {
                    forceState: "ON",
                    forceHueMode: newMode
                });
            }
            return newMode;
        }), "HUE_MODE");
}

/**
 * Sync optional rich inputs on b_action_device from entity type + STATE.
 * Critical: never dispose HUE_MODE / STATE while that field is being edited —
 * only add/remove sibling rows (preset / custom / audio / blinds).
 * opts.forceState / opts.forceHueMode: caller-supplied values (validators / events).
 */
function blockyActionUpdateRichShape(block, opts) {
    if (!block || !window.Blockly || block._richUpdating) return;
    opts = opts || {};
    block._richUpdating = true;
    const Events = Blockly.Events;
    // Blockly 13 refcounts disable/enable — always pair 1:1 (never gate enable on wasEnabled).
    Events.disable();
    try {
        const eid = block.getFieldValue("ENTITY");
        const type = blockyEntityTypeOf(eid);
        const origin = String(blockyEntityOriginOf(eid) || "").toLowerCase();
        const state = String(
            opts.forceState != null ? opts.forceState : (block.getFieldValue("STATE") || "")
        );

        const snap = {};
        ["OPEN_PCT", "HUE_MODE", "PRESET", "VOLUME", "STATION"].forEach((n) => {
            try {
                const f = block.getField(n);
                if (f) snap[n] = f.getValue();
            } catch (e) { /* ignore */ }
        });

        const wantBlinds = type === "blinds" || type === "shutter";
        const wantHue = (type === "light" || type === "hue") && state === "ON";
        const wantAudio = (type === "speaker" || type === "media_player") && state === "ON";

        if (!wantBlinds) blockyRemoveInput(block, "RICH_BLINDS");
        if (!wantHue) {
            blockyRemoveInput(block, "RICH_HUE_MODE");
            blockyRemoveInput(block, "RICH_HUE_PRESET");
            blockyRemoveInput(block, "RICH_HUE_CUSTOM");
        }
        if (!wantAudio) blockyRemoveInput(block, "RICH_AUDIO");

        if (wantBlinds) {
            let st = state;
            if (st !== "OPEN" && st !== "CLOSED" && st !== "POS") {
                st = blockyBlindsUiStateFromStored(st);
                blockyForceDropdownValue(block, "STATE", st);
            }
            if (st === "POS") {
                if (!block.getInput("RICH_BLINDS")) {
                    const openDefault = snap.OPEN_PCT != null ? Number(snap.OPEN_PCT) : 50;
                    block.appendDummyInput("RICH_BLINDS")
                        .appendField("open")
                        .appendField(new Blockly.FieldNumber(
                            Number.isFinite(openDefault) ? openDefault : 50, 0, 100, 1
                        ), "OPEN_PCT")
                        .appendField("%  (stored closed % = 100−open)");
                } else if (snap.OPEN_PCT != null) {
                    blockySafeSetField(block, "OPEN_PCT", snap.OPEN_PCT);
                }
            } else {
                blockyRemoveInput(block, "RICH_BLINDS");
            }
            return;
        }

        if (wantHue) {
            blockyEnsureHueModeInput(block);

            let mode = opts.forceHueMode != null ? opts.forceHueMode : snap.HUE_MODE;
            // Prefer sticky/pending rich over a bare NONE left by an earlier shape rebuild
            // (e.g. coerce before apply, or ENTITY microtask). Do not override an
            // already-committed PRESET/CUSTOM — only upgrade from NONE/invalid.
            if (opts.forceHueMode == null) {
                if (mode !== "PRESET" && mode !== "CUSTOM") {
                    if (block._pendingPreset || snap.PRESET) mode = "PRESET";
                    else if (block._hueBri != null || block._hueXy) mode = "CUSTOM";
                    else mode = "NONE";
                }
            }
            if (mode === "CUSTOM" || mode === "NONE") block._pendingPreset = null;

            // Keep HUE_MODE field — only set its value (do not recreate).
            blockySafeSetField(block, "HUE_MODE", mode);

            if (mode === "PRESET") {
                blockyRemoveInput(block, "RICH_HUE_CUSTOM");
                blockyRemoveHueSwatchField(block);
                const presetOpts = blockyHuePresetOptions(
                    snap.PRESET || block._pendingPreset || ""
                );
                let stickyPreset = snap.PRESET || block._pendingPreset || "";
                if (!stickyPreset || !presetOpts.some((o) => o[1] === stickyPreset)) {
                    stickyPreset = presetOpts[0] ? presetOpts[0][1] : "";
                }
                if (!block.getInput("RICH_HUE_PRESET")) {
                    block.appendDummyInput("RICH_HUE_PRESET")
                        .appendField("preset")
                        .appendField(new Blockly.FieldDropdown(
                            () => blockyHuePresetOptions(
                                block.getFieldValue("PRESET") || block._pendingPreset || stickyPreset
                            )
                        ), "PRESET");
                }
                if (stickyPreset) blockySafeSetField(block, "PRESET", stickyPreset);
            } else if (mode === "CUSTOM") {
                blockyRemoveInput(block, "RICH_HUE_PRESET");
                // Drop legacy third-row "edit color…" chrome (re-select custom opens wheel).
                blockyRemoveInput(block, "RICH_HUE_CUSTOM");
                if (block._hueBri == null) block._hueBri = 100;
                if (!block._hueXy) block._hueXy = [0.4575, 0.4099];
                if (!block._hueHex) {
                    block._hueHex = blockyXyToHex(block._hueXy[0], block._hueXy[1], block._hueBri);
                }
                // Swatch on the same row as color / custom color.
                blockyEnsureHueSwatchField(block);
                blockyPaintHueSwatch(block);
            } else {
                blockyRemoveInput(block, "RICH_HUE_PRESET");
                blockyRemoveInput(block, "RICH_HUE_CUSTOM");
                blockyRemoveHueSwatchField(block);
                // Drop sticky custom so a later bare rebuild does not bounce back to CUSTOM.
                delete block._hueBri;
                delete block._hueXy;
                delete block._hueHex;
            }
            return;
        }

        if (wantAudio) {
            const maxVol = blockyEntityMaxVolume(eid);
            const vol = snap.VOLUME != null && snap.VOLUME !== "" ? Number(snap.VOLUME) : 0;
            const needStation = origin === "sonos";
            const hasAudio = !!block.getInput("RICH_AUDIO");
            const hasStation = !!block.getField("STATION");
            if (!hasAudio || (!!hasStation) !== needStation) {
                blockyRemoveInput(block, "RICH_AUDIO");
                const input = block.appendDummyInput("RICH_AUDIO")
                    .appendField("volume")
                    .appendField(new Blockly.FieldNumber(
                        Number.isFinite(vol) ? Math.min(maxVol, Math.max(0, vol)) : 0,
                        0, maxVol, 1
                    ), "VOLUME");
                if (needStation) {
                    const stickyStation = snap.STATION || block._pendingStation || "";
                    input.appendField("station")
                        .appendField(new Blockly.FieldDropdown(
                            () => blockySonosStationOptions(
                                block.getFieldValue("STATION") || block._pendingStation || stickyStation
                            )
                        ), "STATION");
                    if (stickyStation) blockySafeSetField(block, "STATION", stickyStation);
                    else if (snap.STATION) blockySafeSetField(block, "STATION", snap.STATION);
                }
            } else if (snap.VOLUME != null) {
                blockySafeSetField(block, "VOLUME", snap.VOLUME);
            }
        }
    } finally {
        Events.enable();
        block._richUpdating = false;
        try {
            if (block.rendered && typeof block.render === "function") block.render();
        } catch (e) { /* ignore */ }
        blockyPaintHueSwatch(block);
    }
}

/** Apply YAML/JSON action rich keys onto a block after shape is built (per-action, not by entity). */
function blockyApplyActionRich(block, action) {
    if (!block || !action) return;
    const eid = action.entity_id || block.getFieldValue("ENTITY");
    const type = blockyEntityTypeOf(eid);

    // Seed sticky keys before shape build so FieldDropdown accepts setValue.
    if (action.station) block._pendingStation = String(action.station);
    if (action.preset) block._pendingPreset = String(action.preset);

    if (type === "blinds" || type === "shutter") {
        const ui = blockyBlindsUiStateFromStored(action.state);
        // Must refresh dropdown options first — stale ON/OFF cache rejects CLOSED/POS
        // and coerce then snaps to OPEN (same class of bug as Hue after save→reload).
        blockyForceDropdownValue(block, "STATE", ui);
        blockyActionUpdateRichShape(block, { forceState: ui });
        if (ui === "POS") {
            blockySafeSetField(block, "OPEN_PCT", blockyOpenPctFromStored(action.state));
        }
        return;
    }

    if ((type === "light" || type === "hue") && String(action.state || "").toUpperCase() === "ON") {
        if (action.preset) {
            // forceHueMode — do not let a prior NONE snap wipe _pendingPreset.
            blockyActionUpdateRichShape(block, { forceHueMode: "PRESET" });
            blockySafeSetField(block, "PRESET", action.preset);
        } else if (action.bri != null || action.xy != null) {
            if (action.bri != null) block._hueBri = Number(action.bri);
            if (Array.isArray(action.xy) && action.xy.length >= 2) {
                block._hueXy = [Number(action.xy[0]), Number(action.xy[1])];
            }
            block._hueHex = blockyXyToHex(
                (block._hueXy && block._hueXy[0]) || 0.4575,
                (block._hueXy && block._hueXy[1]) || 0.4099,
                block._hueBri != null ? block._hueBri : 100
            );
            blockyActionUpdateRichShape(block, { forceHueMode: "CUSTOM" });
        } else {
            blockyActionUpdateRichShape(block, { forceHueMode: "NONE" });
        }
        delete block._pendingPreset;
        return;
    }

    if ((type === "speaker" || type === "media_player") && String(action.state || "").toUpperCase() === "ON") {
        blockyActionUpdateRichShape(block);
        if (action.volume != null) blockySafeSetField(block, "VOLUME", Number(action.volume));
        if (action.station) blockySafeSetField(block, "STATION", action.station);
        delete block._pendingStation;
        return;
    }

    blockyActionUpdateRichShape(block);
    delete block._pendingStation;
    delete block._pendingPreset;
}

function blockyReadActionRich(block) {
    const entity = block.getFieldValue("ENTITY");
    const type = blockyEntityTypeOf(entity);
    const origin = String(blockyEntityOriginOf(entity) || "").toLowerCase();
    const out = { entity_id: entity, state: block.getFieldValue("STATE") };

    if (type === "blinds" || type === "shutter") {
        const ui = block.getFieldValue("STATE");
        if (ui === "OPEN") out.state = "0";
        else if (ui === "CLOSED") out.state = "100";
        else {
            const openPct = block.getFieldValue("OPEN_PCT");
            out.state = blockyStoredFromOpenPct(openPct != null ? openPct : 50);
        }
        return out;
    }

    if ((type === "light" || type === "hue") && out.state === "ON") {
        const mode = block.getFieldValue("HUE_MODE") || "NONE";
        if (mode === "PRESET") {
            const preset = block.getFieldValue("PRESET");
            if (preset) out.preset = preset;
        } else if (mode === "CUSTOM") {
            const bri = block._hueBri;
            const xy = block._hueXy;
            if (bri != null && !Number.isNaN(Number(bri))) out.bri = Number(bri);
            if (Array.isArray(xy) && xy.length >= 2) {
                const x = Number(xy[0]);
                const y = Number(xy[1]);
                if (!Number.isNaN(x) && !Number.isNaN(y)) out.xy = [x, y];
            }
        }
        return out;
    }

    if ((type === "speaker" || type === "media_player") && out.state === "ON") {
        const vol = block.getFieldValue("VOLUME");
        if (vol !== "" && vol != null) {
            const n = Number(vol);
            if (!Number.isNaN(n)) out.volume = n;
        }
        if (origin === "sonos") {
            const station = block.getFieldValue("STATION");
            if (station) out.station = station;
        }
        return out;
    }

    return out;
}

function blockyCoerceFieldToOptions(block, fieldName, optionsFn) {
    try {
        const f = block.getField(fieldName);
        if (!f) return;
        // Refresh dynamic menu before setValue — stale cache rejects valid new values
        // (e.g. light ON/OFF cache rejecting blinds OPEN).
        try { f.getOptions(false); } catch (e) { /* ignore */ }
        const opts = optionsFn(block);
        if (!opts || !opts.length) return;
        let v = f.getValue();
        // Legacy FORCE_* on always-forced origins → plain ON/OFF before menu coerce.
        if (fieldName === "STATE" && typeof v === "string" && v.startsWith("FORCE_")) {
            const stripped = v.slice("FORCE_".length);
            if (opts.some((o) => o[1] === stripped)) {
                f.setValue(stripped);
                if (typeof f.forceRerender === "function") f.forceRerender();
                return;
            }
        }
        // Blinds may still hold a stored closed-% ("100") or light leftover ("ON") after
        // mkBlock — map closed-% before falling through to opts[0] (OPEN).
        if (fieldName === "STATE" && !opts.some((o) => o[1] === v)) {
            const et = blockyEntityTypeOf(block.getFieldValue("ENTITY"));
            if (et === "blinds" || et === "shutter") {
                const mapped = blockyBlindsUiStateFromStored(v);
                if (opts.some((o) => o[1] === mapped)) {
                    f.setValue(mapped);
                    if (typeof f.forceRerender === "function") f.forceRerender();
                    return;
                }
            }
        }
        if (!opts.some((o) => o[1] === v)) {
            f.setValue(opts[0][1]);
        }
        if (typeof f.forceRerender === "function") f.forceRerender();
    } catch (e) { /* ignore */ }
}

/** Set a dynamic dropdown value after refreshing its option list. */
function blockyForceDropdownValue(block, fieldName, value) {
    if (!block || value == null || value === "") return;
    const f = block.getField(fieldName);
    if (!f) return;
    try { f.getOptions(false); } catch (e) { /* ignore */ }
    try { f.setValue(String(value)); } catch (e) { /* ignore */ }
    if (typeof f.forceRerender === "function") f.forceRerender();
}

function blockyRefreshCaseMatchLabels(fromBlock) {
    let cur = fromBlock;
    while (cur) {
        if (cur.type === "b_case") {
            const f = cur.getField("MATCH");
            if (f) {
                try {
                    const opts = blockyCaseMatchOptions(cur);
                    const v = f.getValue();
                    f.getOptions(false);
                    if (!opts.some((o) => o[1] === v)) {
                        f.setValue(opts[0][1]);
                    } else {
                        f.setValue(v);
                    }
                    if (typeof f.forceRerender === "function") f.forceRerender();
                } catch (e) { /* ignore */ }
            }
        }
        cur = cur.getNextBlock ? cur.getNextBlock() : null;
    }
}

function defineBlockyBlocks(Blockly, providers) {
    const entityTriggerDd = providers.entityTrigger || providers.entity;
    const entityConditionDd = providers.entityCondition || providers.entity;
    const entityActionDd = providers.entityAction || providers.entity;
    const familyDd = providers.family;
    const eventDd = providers.event;

    Object.keys(Blockly.Blocks).forEach((t) => {
        if (t.startsWith("b_")) delete Blockly.Blocks[t];
    });

    Blockly.Blocks.b_trig_device = {
        init() {
            this.appendDummyInput()
                .appendField("When device")
                .appendField(new Blockly.FieldDropdown(entityTriggerDd), "ENTITY")
                .appendField("(use cases for ON/OFF)");
            this.setNextStatement(true, "Case");
            this.setColour(230);
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && (ev.type === "create" || ev.type === "move"
                || (ev.type === "change" && ev.name === "ENTITY"))) {
                blockyRefreshCaseMatchLabels(this.getNextBlock());
            }
        }
    };
    Blockly.Blocks.b_trig_device_edge = {
        init() {
            const block = this;
            this.appendDummyInput()
                .appendField("When device")
                .appendField(new Blockly.FieldDropdown(entityTriggerDd), "ENTITY")
                .appendField("becomes")
                .appendField(new Blockly.FieldDropdown(() => blockyEdgeStateOptions(block)), "STATE");
            this.setPreviousStatement(true, "TrigEdge");
            this.setNextStatement(true, "TrigEdge");
            this.setColour(230);
            this.setTooltip("OR-list edge only — put inside “When any of”. For a single device use “When device” + cases.");
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && ev.type === "change" && ev.name === "ENTITY") {
                blockyCoerceFieldToOptions(this, "STATE", blockyEdgeStateOptions);
            }
        }
    };
    Blockly.Blocks.b_trig_event_edge = {
        init() {
            this.appendDummyInput()
                .appendField("When event")
                .appendField(new Blockly.FieldDropdown(eventDd), "EVENT");
            this.setPreviousStatement(true, "TrigEdge");
            this.setNextStatement(true, "TrigEdge");
            this.setColour(210);
            this.setTooltip("OR-list edge only — put inside “When any of”.");
        }
    };
    Blockly.Blocks.b_trig_or = {
        init() {
            this.appendDummyInput().appendField("When any of");
            this.appendStatementInput("EDGES").setCheck("TrigEdge");
            this.setNextStatement(true, "Case");
            this.setColour(220);
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && (ev.type === "create" || ev.type === "move")) {
                blockyRefreshCaseMatchLabels(this.getNextBlock());
            }
        }
    };
    Blockly.Blocks.b_trig_event = {
        init() {
            this.appendDummyInput()
                .appendField("When event")
                .appendField(new Blockly.FieldDropdown(eventDd), "EVENT");
            this.setNextStatement(true, "Case");
            this.setColour(210);
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && (ev.type === "create" || ev.type === "move")) {
                blockyRefreshCaseMatchLabels(this.getNextBlock());
            }
        }
    };
    Blockly.Blocks.b_trig_family = {
        init() {
            const block = this;
            this.appendDummyInput()
                .appendField("When start or end")
                .appendField(new Blockly.FieldDropdown(familyDd, (newVal) => {
                    block.updateScheduleHint_(newVal);
                    blockyRefreshCaseMatchLabels(block.getNextBlock());
                    return newVal;
                }), "FAMILY");
            this.appendDummyInput("HINT")
                .appendField(new Blockly.FieldLabel(""), "HINT");
            this.setNextStatement(true, "Case");
            this.setColour(210);
        },
        updateScheduleHint_(fam) {
            const hint = this.getField("HINT");
            if (!hint) return;
            hint.setValue(blockyScheduleWindowHint(fam || this.getFieldValue("FAMILY")));
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            // Keep hint + case labels in sync after load / move
            if (!ev || ev.type === "create" || ev.type === "move" || ev.type === "change") {
                this.updateScheduleHint_(this.getFieldValue("FAMILY"));
                if (ev && ev.type === "change" && ev.name === "FAMILY") {
                    blockyRefreshCaseMatchLabels(this.getNextBlock());
                }
            }
        }
    };

    Blockly.Blocks.b_case = {
        init() {
            const block = this;
            this.appendDummyInput()
                .appendField("if")
                .appendField(new Blockly.FieldDropdown(() => blockyCaseMatchOptions(block)), "MATCH");
            this.appendDummyInput().appendField("conditions");
            this.appendStatementInput("CONDS").setCheck("Condition");
            this.appendDummyInput().appendField("actions");
            this.appendStatementInput("ACTIONS").setCheck("Action");
            this.setPreviousStatement(true, "Case");
            this.setNextStatement(true, "Case");
            this.setColour(120);
            this.setInputsInline(false);
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && (ev.type === "move" || ev.type === "create")) {
                blockyCoerceFieldToOptions(this, "MATCH", blockyCaseMatchOptions);
                const f = this.getField("MATCH");
                if (f) {
                    try {
                        const v = f.getValue();
                        f.setValue(v);
                        if (typeof f.forceRerender === "function") f.forceRerender();
                    } catch (e) { /* ignore */ }
                }
            }
        }
    };

    Blockly.Blocks.b_condition_device = {
        init() {
            const block = this;
            this.appendDummyInput()
                .appendField("if device")
                .appendField(new Blockly.FieldDropdown(entityConditionDd), "ENTITY")
                .appendField("is")
                .appendField(new Blockly.FieldDropdown(() => blockyConditionStateOptions(block)), "STATE");
            this.setPreviousStatement(true, "Condition");
            this.setNextStatement(true, "Condition");
            this.setColour(60);
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && ev.type === "change" && ev.name === "ENTITY") {
                blockyCoerceFieldToOptions(this, "STATE", blockyConditionStateOptions);
            }
        }
    };
    Blockly.Blocks.b_condition_time = {
        init() {
            this.appendDummyInput()
                .appendField("if time is")
                .appendField(new Blockly.FieldDropdown([["dark", "dark"], ["light", "light"]]), "TOD");
            this.setPreviousStatement(true, "Condition");
            this.setNextStatement(true, "Condition");
            this.setColour(60);
        }
    };
    Blockly.Blocks.b_action_device = {
        init() {
            const block = this;
            this.appendDummyInput("MAIN")
                .appendField("set device")
                .appendField(new Blockly.FieldDropdown(entityActionDd, (newEid) => {
                    // Validator runs before commit — ENTITY field still holds previous id.
                    const prevEid = block.getFieldValue("ENTITY");
                    const prevType = blockyEntityTypeOf(prevEid);
                    const nextType = blockyEntityTypeOf(newEid);
                    queueMicrotask(() => {
                        // Load path applies rich itself — do not clear sticky after mkBlock setField.
                        if (BlockyRT.loading) return;
                        let forceSt = null;
                        if (prevEid && prevType !== nextType) {
                            blockyClearActionRichSticky(block);
                            if (nextType === "blinds" || nextType === "shutter") forceSt = "OPEN";
                            else if (nextType === "light" || nextType === "hue") forceSt = "ON";
                        }
                        if (forceSt) {
                            blockyForceDropdownValue(block, "STATE", forceSt);
                        }
                        // Always coerce so invalid leftovers (ON on blinds) snap to OPEN/etc.
                        blockyCoerceFieldToOptions(block, "STATE", blockyActionStateOptions);
                        if (forceSt && block.getFieldValue("STATE") !== forceSt) {
                            blockyForceDropdownValue(block, "STATE", forceSt);
                        }
                        const st = block.getFieldValue("STATE") || forceSt;
                        blockyQueueRichShape(block, { forceState: st });
                        if (BlockyRT.app) BlockyRT.app.markEditorDirty();
                    });
                    return newEid;
                }), "ENTITY")
                .appendField("to")
                .appendField(new Blockly.FieldDropdown(
                    () => blockyActionStateOptions(block),
                    (newState) => {
                        if (!BlockyRT.loading) {
                            blockyQueueRichShape(block, { forceState: newState });
                        }
                        return newState;
                    }
                ), "STATE");
            this.setPreviousStatement(true, "Action");
            this.setNextStatement(true, "Action");
            this.setColour(290);
            blockyActionUpdateRichShape(this);
        },
        // Shape updates come from field validators + blockyQueueRichShape (not onchange).
        onchange() { /* intentional no-op */ }
    };
    Blockly.Blocks.b_action_event = {
        init() {
            this.appendDummyInput()
                .appendField("fire event")
                .appendField(new Blockly.FieldDropdown(eventDd), "EVENT");
            this.setPreviousStatement(true, "Action");
            this.setNextStatement(true, "Action");
            this.setColour(290);
        }
    };
}

function blockyToolboxDefinition(_presentTypes) {
    // Trigger flyout always available so operators can replace a deleted root.
    // Uniqueness still enforces one blue root on the canvas (extras are dropped).
    const contents = [
        {
            kind: "category",
            name: "Trigger",
            colour: "#5C81A6",
            contents: [
                { kind: "block", type: "b_trig_device" },
                { kind: "block", type: "b_trig_or" },
                { kind: "block", type: "b_trig_event" },
                { kind: "block", type: "b_trig_family" }
            ]
        }
    ];
    let showOrEdges = false;
    try {
        const ws = blockyWs();
        if (ws) {
            const roots = ws.getTopBlocks(false).filter((b) => BLOCKY_ROOT_TRIGGERS.has(b.type));
            showOrEdges = roots.some((b) => b.type === "b_trig_or");
        }
    } catch (e) { /* ignore */ }
    // OR edges only snap inside “When any of” — hide the category otherwise.
    if (showOrEdges) {
        contents.push({
            kind: "category",
            name: "OR edges",
            colour: "#6B8CAE",
            contents: [
                { kind: "block", type: "b_trig_device_edge" },
                { kind: "block", type: "b_trig_event_edge" }
            ]
        });
    }
    contents.push(
        {
            kind: "category",
            name: "Cases",
            colour: "#5CA65C",
            contents: [{ kind: "block", type: "b_case" }]
        },
        {
            kind: "category",
            name: "Conditions",
            colour: "#A6745C",
            contents: [
                { kind: "block", type: "b_condition_device" },
                { kind: "block", type: "b_condition_time" }
            ]
        },
        {
            kind: "category",
            name: "Actions",
            colour: "#A65C81",
            contents: [
                { kind: "block", type: "b_action_device" },
                { kind: "block", type: "b_action_event" }
            ]
        }
    );
    return { kind: "categoryToolbox", contents };
}

const BlockyRT = {
    ws: null,
    ready: false,
    schemaInjected: null,
    loading: false,
    enforcing: false,
    uniquenessScheduled: false,
    uniquenessTimer: null,
    pendingFieldEv: null,
    pendingCreateRootId: null,
    resizeObserver: null,
    windowResize: null,
    app: null,
    colorPicker: null,
    pendingRichOpts: null,
    richTimer: null,
    suppressHueWheel: false
};

function blockyWs() {
    return BlockyRT.ws;
}

function blockyFingerprint(block) {
    if (!block) return "";
    const t = block.type;
    if (BLOCKY_ROOT_TRIGGERS.has(t)) return "trigger";
    try {
        if (t === "b_condition_device") {
            return `cond:device:${block.getFieldValue("ENTITY")}:${block.getFieldValue("STATE")}`;
        }
        if (t === "b_condition_time") return `cond:time:${block.getFieldValue("TOD")}`;
        if (t === "b_action_device") {
            const eid = block.getFieldValue("ENTITY");
            const type = blockyEntityTypeOf(eid);
            if (type === "blinds" || type === "shutter") {
                const ui = block.getFieldValue("STATE");
                if (ui === "POS") {
                    return `act:device:${eid}:open:${block.getFieldValue("OPEN_PCT")}`;
                }
                return `act:device:${eid}:${ui || "OPEN"}`;
            }
            return `act:device:${eid}:${block.getFieldValue("STATE")}`;
        }
        if (t === "b_action_event") return `act:event:${block.getFieldValue("EVENT")}`;
        // Cases and OR edges are allowed as multiples — no fingerprint
    } catch (e) { /* ignore */ }
    return "";
}

function blockyRefreshToolbox() {
    const ws = blockyWs();
    if (!ws) return;
    const present = new Set(ws.getAllBlocks(false).map((b) => b.type));
    try { ws.updateToolbox(blockyToolboxDefinition(present)); } catch (e) { /* ignore */ }
}

function blockyCancelUniqueness() {
    if (BlockyRT.uniquenessTimer) {
        clearTimeout(BlockyRT.uniquenessTimer);
        BlockyRT.uniquenessTimer = null;
    }
    BlockyRT.uniquenessScheduled = false;
    BlockyRT.pendingFieldEv = null;
    BlockyRT.pendingCreateRootId = null;
    // Do not clear richTimer / pendingRichOpts — field validators own that path.
}

function blockyBlockCaseScope(b) {
    let p = b;
    while (p) {
        if (p.type === "b_case") return p.id;
        try { p = p.getParent(); } catch (e) { break; }
    }
    return "top";
}

function blockyEnforceUniqueness(forceToolbox) {
    const ws = blockyWs();
    if (BlockyRT.loading || BlockyRT.enforcing || !ws || !window.Blockly) return;
    // Rich-shape mutate + uniqueness both use timeout 0 — never dispose mid-reshape
    // (dispose without heal was leaving “not snapped” orphans on Save).
    if (BlockyRT.richTimer || BlockyRT.pendingRichOpts) {
        if (!BlockyRT.uniquenessScheduled) {
            BlockyRT.uniquenessScheduled = true;
            BlockyRT.uniquenessTimer = setTimeout(() => {
                BlockyRT.uniquenessScheduled = false;
                BlockyRT.uniquenessTimer = null;
                blockyEnforceUniqueness(forceToolbox);
            }, 0);
        }
        return;
    }
    BlockyRT.enforcing = true;
    const Events = Blockly.Events;
    const fieldEv = BlockyRT.pendingFieldEv;
    BlockyRT.pendingFieldEv = null;
    let changed = !!forceToolbox;
    Events.disable();
    try {
        if (fieldEv && fieldEv.element === "field" && fieldEv.blockId) {
            const blk = ws.getBlockById(fieldEv.blockId);
            if (blk) {
                const fp = blockyFingerprint(blk);
                // Scope by case — ON-case Sonos OFF must not collide with OFF-case Sonos OFF.
                const scope = blockyBlockCaseScope(blk);
                const other = fp && ws.getAllBlocks(false).find((b) => (
                    b.id !== blk.id
                    && !b.isInsertionMarker
                    && blockyFingerprint(b) === fp
                    && blockyBlockCaseScope(b) === scope
                ));
                if (other) {
                    try { blk.setFieldValue(fieldEv.oldValue, fieldEv.name); } catch (e) { /* ignore */ }
                    if (blk.type === "b_action_device"
                        && (fieldEv.name === "STATE" || fieldEv.name === "ENTITY" || fieldEv.name === "HUE_MODE")) {
                        blockyActionUpdateRichShape(blk);
                    }
                    changed = true;
                }
            }
        }
        // Only one root trigger — keep the existing rule; reject extras.
        const roots = ws.getTopBlocks(false).filter((b) => BLOCKY_ROOT_TRIGGERS.has(b.type));
        if (roots.length > 1) {
            const newId = BlockyRT.pendingCreateRootId;
            let keep = roots.find((b) => !newId || b.id !== newId) || roots[0];
            let rejected = false;
            roots.forEach((b) => {
                if (b.id === keep.id) return;
                // healStack true — keep case chain attached to the surviving trigger.
                try { b.dispose(true); changed = true; rejected = true; } catch (e) { /* ignore */ }
            });
            blockyRefreshCaseMatchLabels(keep.getNextBlock());
            if (rejected && BlockyRT.app) {
                BlockyRT.app.infoMessage =
                    "Only one trigger per rule — delete the current blue block before adding another type.";
            }
        }
        BlockyRT.pendingCreateRootId = null;
        const seen = new Map();
        const toDispose = [];
        ws.getAllBlocks(false).forEach((b) => {
            if (b.isInsertionMarker) return;
            const fp = blockyFingerprint(b);
            if (!fp || fp === "trigger") return;
            // Immediate parent scope: allows same device twice in one case (per-action rich).
            const parent = b.getParent();
            const scope = parent ? parent.id : "top";
            const key = `${scope}::${fp}`;
            if (seen.has(key)) toDispose.push(b);
            else seen.set(key, b.id);
        });
        toDispose.forEach((b) => {
            // healStack true — do not leave the next action as a floating orphan.
            try { b.dispose(true); changed = true; } catch (e) { /* ignore */ }
        });
    } finally {
        Events.enable();
        BlockyRT.enforcing = false;
        // Always refresh — OR-edges category depends on whether root is “When any of”.
        blockyRefreshToolbox();
    }
}

function blockyOnChange(ev) {
    if (!blockyWs() || !ev) return;
    // Selection / UI — refresh Delete button enabled state.
    if (ev.isUiEvent) {
        if (BlockyRT.app) {
            // Blockly Selected: newElementId is the block id (or null when cleared).
            const selType = Blockly.Events && Blockly.Events.SELECTED;
            if (ev.type === selType || ev.type === "selected" || ev.element === "selected") {
                const nid = ev.newElementId != null ? ev.newElementId : ev.newValue;
                BlockyRT.app._blocklySelectedId = nid || null;
            } else if (typeof BlockyRT.app._captureSelectedBlock === "function") {
                BlockyRT.app._captureSelectedBlock();
            }
            BlockyRT.app.blocklyUiTick = (BlockyRT.app.blocklyUiTick || 0) + 1;
        }
        return;
    }
    if (BlockyRT.loading) return;
    const Events = Blockly.Events;
    const t = ev.type;
    const isCreate = t === Events.BLOCK_CREATE || t === "create";
    const isChange = (t === Events.BLOCK_CHANGE || t === "change") && ev.element === "field";
    // Connect or disconnect (not free XY nudges — those are not in saved JSON).
    const isMoveRelink = (t === Events.BLOCK_MOVE || t === "move") && (!!ev.newParentId || !!ev.oldParentId);
    const isDelete = t === Events.BLOCK_DELETE || t === "delete";
    if (!isCreate && !isChange && !isMoveRelink && !isDelete) return;

    // Mark dirty immediately. The uniqueness timer below can be cancelled (e.g. by
    // loadV2IntoBlockly → blockyCancelUniqueness) and must not be the only dirty path.
    if (BlockyRT.app) BlockyRT.app.markEditorDirty();

    if (isCreate) {
        const ws = blockyWs();
        const ids = ev.ids || (ev.blockId ? [ev.blockId] : []);
        ids.forEach((id) => {
            const b = ws && ws.getBlockById(id);
            if (b && BLOCKY_ROOT_TRIGGERS.has(b.type)) {
                BlockyRT.pendingCreateRootId = b.id;
            }
        });
    }
    let touchedActionId = null;
    if (isChange) {
        BlockyRT.pendingFieldEv = ev;
        // Backup path: field validators usually queue rich shape; this covers setFieldValue.
        if (ev.blockId && (ev.name === "STATE" || ev.name === "ENTITY" || ev.name === "HUE_MODE")) {
            const ws = blockyWs();
            const blk = ws && ws.getBlockById(ev.blockId);
            if (blk && blk.type === "b_action_device") {
                touchedActionId = blk.id;
                const opts = {};
                if (ev.name === "STATE") opts.forceState = ev.newValue;
                if (ev.name === "HUE_MODE") {
                    opts.forceHueMode = ev.newValue;
                    opts.forceState = "ON";
                    if (ev.newValue === "CUSTOM" && !BlockyRT.suppressHueWheel) opts.openWheel = true;
                }
                blockyQueueRichShape(blk, opts);
            }
        }
    }
    if (BlockyRT.uniquenessScheduled) return;
    BlockyRT.uniquenessScheduled = true;
    BlockyRT.uniquenessTimer = setTimeout(() => {
        BlockyRT.uniquenessScheduled = false;
        BlockyRT.uniquenessTimer = null;
        blockyEnforceUniqueness(false);
        // After uniqueness may revert STATE — re-sync from live fields (skip if a
        // richer queued update with force* / openWheel is already pending).
        if (touchedActionId && !BlockyRT.pendingRichOpts) {
            const ws = blockyWs();
            const blk = ws && ws.getBlockById(touchedActionId);
            if (blk && blk.type === "b_action_device") {
                blockyActionUpdateRichShape(blk);
            }
        }
        if (BlockyRT.app) {
            BlockyRT.app.blocklyUiTick = (BlockyRT.app.blocklyUiTick || 0) + 1;
            if (!BlockyRT.app.canShowOnDashboard) {
                BlockyRT.app.editor.scene = false;
                BlockyRT.app.editor.require_confirmation = false;
            }
        }
    }, 0);
}

function blockyMkBlock(type, fields, x, y) {
    const ws = blockyWs();
    const b = ws.newBlock(type);
    if (fields) {
        Object.entries(fields).forEach(([k, v]) => {
            if (v == null || v === "") return;
            try {
                b.setFieldValue(String(v), k);
            } catch (e) {
                // Usually means eid missing from dropdown — open-rule inject should prevent this.
                console.warn(`Blocky: could not set ${type}.${k}=${v}`, e);
            }
        });
    }
    if (typeof x === "number" && typeof y === "number") b.moveBy(x, y);
    if (b.initSvg) b.initSvg();
    b.render();
    return b;
}

function blockyConnectChain(parent, inputName, blocks) {
    const input = parent.getInput(inputName);
    if (!input || !input.connection) return;
    let prevConn = input.connection;
    blocks.forEach((b) => {
        if (!b || !b.previousConnection) return;
        try {
            prevConn.connect(b.previousConnection);
            prevConn = b.nextConnection;
        } catch (e) { /* skip */ }
    });
}

function blockyConnectNext(start, blocks) {
    let prev = start;
    blocks.forEach((b) => {
        if (!prev || !b || !prev.nextConnection || !b.previousConnection) return;
        try {
            prev.nextConnection.connect(b.previousConnection);
            prev = b;
        } catch (e) { /* skip */ }
    });
    return prev;
}

function blockyDestroyWorkspace() {
    blockyCancelUniqueness();
    if (BlockyRT.richTimer) {
        clearTimeout(BlockyRT.richTimer);
        BlockyRT.richTimer = null;
    }
    BlockyRT.pendingRichOpts = null;
    if (BlockyRT.resizeObserver) {
        try { BlockyRT.resizeObserver.disconnect(); } catch (e) { /* ignore */ }
        BlockyRT.resizeObserver = null;
    }
    if (BlockyRT.ws) {
        try { BlockyRT.ws.dispose(); } catch (e) { /* ignore */ }
    }
    BlockyRT.ws = null;
    BlockyRT.ready = false;
    BlockyRT.schemaInjected = null;
    const host = document.getElementById("blocklyWorkspace");
    if (host) host.innerHTML = "";
}

function blockyOrphanLeaves(ws) {
    return ws.getAllBlocks(false).filter((b) => {
        if (!b) return false;
        if (b.isInsertionMarker) return false;
        if (typeof b.isDeadOrDying === "function" && b.isDeadOrDying()) return false;
        if (BLOCKY_ROOT_TRIGGERS.has(b.type)) return false;
        if (b.type === "b_case") {
            const prev = b.previousConnection;
            return !(prev && prev.isConnected());
        }
        // trig edges may be inside OR
        if (b.type === "b_trig_device_edge" || b.type === "b_trig_event_edge") {
            const p = b.getParent();
            if (p && p.type === "b_trig_or") return false;
            return true; // must live inside “When any of”
        }
        if (b.type === "b_condition_device" || b.type === "b_condition_time"
            || b.type === "b_action_device" || b.type === "b_action_event") {
            // Statement stacks: previousConnection is authoritative (getParent can lag).
            const prev = b.previousConnection;
            return !(prev && prev.isConnected());
        }
        return false;
    });
}

function blockyAssertNoOrphans(ws) {
    const orphans = blockyOrphanLeaves(ws);
    if (!orphans.length) return;
    throw new Error(
        `Save blocked: ${orphans.length} block(s) not snapped into place — connect or delete them.`
    );
}

function blockyReadChain(start, fn) {
    const out = [];
    let cur = start;
    while (cur) {
        out.push(fn(cur));
        cur = cur.getNextBlock();
    }
    return out;
}

function blockyApp() {
    return {
        connected: false,
        busy: false,
        isAdmin: false,
        errorMessage: "",
        infoMessage: "",
        registryCheckMessage: "",
        registryCheckOk: null,
        filterText: "",
        automations: [],
        selectedRule: null,
        entityOptions: [],
        huePresets: {},
        sonosStations: {},
        blockyColorTargetId: null,
        blockyColorBri: 100,
        blockyColorHex: "#FFD180",
        showHiddenEntities: false,
        editorMode: "blockly",
        editorDirty: false,
        suppressDirtyUntil: 0,
        pendingNav: null,
        blocklyFullscreen: false,
            blocklySchemaVersion: 44,
        blocklyUiTick: 0,
        eventFamilies: ["blinds", "twilight_evening", "twilight_morning", "sauna", "ir", "cinema"],
        eventFamilyLabels: {
            blinds: "Blinds open & close",
            twilight_evening: "Twilight evening: sunset & evening-off",
            twilight_morning: "Twilight morning: morning-on & sunrise",
            sauna: "Sauna on & off",
            ir: "IR on & off",
            cinema: "Cinema on & off"
        },
        curatedEvents: [
            "BLINDS_OPEN_TRIGGER", "BLINDS_CLOSE_TRIGGER",
            "MORNING_ON_TRIGGER", "SUNRISE_TRIGGER",
            "SUNSET_TRIGGER", "EVENING_OFF_TRIGGER",
            "SAUNA_ON", "SAUNA_OFF", "IR_ON", "IR_OFF",
            "SCENE_CINEMA_ON", "SCENE_CINEMA_OFF", "SCENE_ALL_OFF", "SCENE_GOCOSY",
            "SCENE_GV_OFF", "SCENE_VERDIEP1_OFF", "SCENE_VERDIEP2_OFF"
        ],
        hardDenyEntityIds: ["switch.safety.safety_wisc_5v"],
        editor: {
            id: "",
            name: "",
            scene: false,
            require_confirmation: false,
            ruleJson: "{}"
        },

        get filteredRules() {
            const q = this.filterText.trim().toLowerCase();
            if (!q) return this.automations;
            return this.automations.filter((r) => {
                const name = (r.name || "").toLowerCase();
                const id = String(r.id || "").toLowerCase();
                return name.includes(q) || id.includes(q);
            });
        },

        /** Exclusive like Device Explorer: ON = only soft-hidden; OFF = only non-hidden. */
        get visibleEntityOptions() {
            return this.entityOptions.filter((opt) =>
                this.showHiddenEntities ? opt.softHidden : !opt.softHidden
            );
        },

        get showBlocklyWorkspace() {
            return !!(this.selectedRule && this.editorMode === "blockly");
        },

        /** Dashboard scenes need an event trigger (device rules cannot appear as buttons). */
        triggerAllowsDashboard(trigger) {
            if (!trigger) return false;
            if (Array.isArray(trigger)) {
                if (!trigger.length) return false;
                return trigger.every((t) => t && t.event && !t.entity_id);
            }
            return !!(trigger.event && !trigger.entity_id);
        },

        get canShowOnDashboard() {
            void this.blocklyUiTick;
            if (this.editorMode === "blockly" && blockyWs()) {
                try {
                    const root = blockyWs().getTopBlocks(false).find((b) => BLOCKY_ROOT_TRIGGERS.has(b.type));
                    if (root) {
                        if (root.type === "b_trig_event" || root.type === "b_trig_family") return true;
                        if (root.type === "b_trig_or") {
                            let e = root.getInputTargetBlock("EDGES");
                            let hasEvent = false;
                            let hasDevice = false;
                            while (e) {
                                if (e.type === "b_trig_event_edge") hasEvent = true;
                                if (e.type === "b_trig_device_edge") hasDevice = true;
                                e = e.getNextBlock();
                            }
                            return hasEvent && !hasDevice;
                        }
                        return false;
                    }
                } catch (e) { /* ignore */ }
            }
            try {
                const rule = JSON.parse(this.editor.ruleJson || "{}");
                return this.triggerAllowsDashboard(rule.trigger);
            } catch (e) {
                return false;
            }
        },

        /** List badges: only dashboard (kiosk scene) and event (incl. family windows). */
        ruleListKind(rule) {
            if (!rule || rule.isDraft) return null;
            if (rule.scene) return "dashboard";
            let t = rule.trigger;
            if (Array.isArray(t) && t.length === 1) t = t[0];
            // OR of events still counts as event-triggered
            if (Array.isArray(t)) {
                if (t.length && t.every((x) => x && x.event && !x.entity_id)) return "event";
                return null;
            }
            if (t && t.event && !t.entity_id) return "event";
            return null;
        },

        ruleListBadgeClass(rule) {
            const k = this.ruleListKind(rule);
            if (k === "dashboard") return "badge-secondary";
            if (k === "event") return "badge-warning";
            return "";
        },

        deviceTypeLabel(type, origin, idx) {
            const t = String(type || "").toLowerCase();
            let o = String(origin || "").toLowerCase();
            if ((t === "speaker" || t === "media_player") && !o) {
                const n = Number(idx);
                if (n >= 60000 && n < 61000) o = "sonos";
                else if (n >= 61000 && n < 62000) o = "onkyo";
            }
            if (t === "speaker" || t === "media_player") {
                if (o === "onkyo") return "Onkyo";
                if (o === "sonos") return "Sonos";
                return "speaker";
            }
            const map = {
                blinds: "blinds", switch: "switch", light: "light", hue: "light",
                scene: "scene", motion: "motion"
            };
            return map[t] || t || "device";
        },

        entityDisplayLabel(opt) {
            if (opt && opt.typeLabel) return `${opt.name} · ${opt.typeLabel}`;
            return `${opt.name} · ${this.deviceTypeLabel(opt.type, opt.origin, opt.idx)}`;
        },

        eventFamilyLabel(fam) {
            return this.eventFamilyLabels[fam] || fam;
        },

        markEditorDirty() {
            if (BlockyRT.loading || Date.now() < (this.suppressDirtyUntil || 0)) return;
            if (!this.selectedRule) return;
            this.editorDirty = true;
            this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
        },

        get hasBlocklySelection() {
            void this.blocklyUiTick;
            const ws = blockyWs();
            if (!ws) return false;
            if (this._blocklySelectedId && ws.getBlockById(this._blocklySelectedId)) return true;
            return !!this._captureSelectedBlock();
        },

        _captureSelectedBlock() {
            if (!window.Blockly || !blockyWs()) return null;
            let sel = null;
            try {
                if (typeof Blockly.getSelected === "function") sel = Blockly.getSelected();
                else if (Blockly.common && typeof Blockly.common.getSelected === "function") {
                    sel = Blockly.common.getSelected();
                }
            } catch (e) { /* ignore */ }
            if (!sel || sel.isInFlyout || sel.workspace !== blockyWs()) return null;
            this._blocklySelectedId = sel.id;
            return sel;
        },

        /** mousedown.prevent on Delete — capture id before Blockly clears selection on button focus. */
        onDeletePointerDown(ev) {
            if (ev) ev.preventDefault();
            this._captureSelectedBlock();
            this._deleteTargetId = this._blocklySelectedId || null;
        },

        deleteSelectedBlock() {
            const ws = blockyWs();
            if (!ws) return;
            const id = this._deleteTargetId || this._blocklySelectedId;
            this._deleteTargetId = null;
            let sel = id ? ws.getBlockById(id) : null;
            if (!sel) sel = this._captureSelectedBlock();
            if (!sel || sel.isInFlyout) return;
            try {
                sel.dispose(true);
            } catch (e) {
                try { sel.dispose(false); } catch (e2) { /* ignore */ }
            }
            this._blocklySelectedId = null;
            this.markEditorDirty();
            this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
        },

        applyBlockyHueColor() {
            blockyApplyHueColorModal();
        },

        closeBlockyHueColor() {
            blockyCloseHueColorModal();
        },

        markEditorClean() {
            this.editorDirty = false;
            this.suppressDirtyUntil = Date.now() + 400;
        },

        requestLeave(action) {
            if (!this.editorDirty) {
                this.runLeaveAction(action);
                return;
            }
            this.pendingNav = action;
            const dlg = document.getElementById("unsaved_rule_modal");
            if (dlg) dlg.showModal();
        },

        runLeaveAction(action) {
            if (!action) return;
            if (action.type === "select") this._doSelectRule(action.rule);
            else if (action.type === "new") this._doNewRule();
            else if (action.type === "href" && action.url) window.location.href = action.url;
            else if (action.type === "reload") this.loadV2IntoBlockly();
            else if (action.type === "logout") this.logout();
        },

        cancelUnsavedLeave() {
            this.pendingNav = null;
            document.getElementById("unsaved_rule_modal")?.close();
        },

        discardUnsavedLeave() {
            const action = this.pendingNav;
            this.pendingNav = null;
            this.markEditorClean();
            document.getElementById("unsaved_rule_modal")?.close();
            this.runLeaveAction(action);
        },

        async saveUnsavedLeave() {
            await this.saveRule();
            if (this.errorMessage) return;
            const action = this.pendingNav;
            this.pendingNav = null;
            document.getElementById("unsaved_rule_modal")?.close();
            // saveRule already reselected the saved rule; still honor leave target.
            this.runLeaveAction(action);
        },

        navAway(ev, url) {
            if (!this.editorDirty) return;
            ev.preventDefault();
            this.requestLeave({ type: "href", url });
        },

        onEditorModeChanged() {
            this.blocklyFullscreen = false;
            if (this.editorMode === "json") {
                try {
                    if (blockyWs()) this.applyBlocklyToV2();
                } catch (e) { /* keep existing ruleJson if canvas incomplete */ }
                return;
            }
            this.scheduleBlocklyLoad();
        },

        blocklyHostReady() {
            const host = document.getElementById("blocklyWorkspace");
            if (!host) return null;
            if ((host.offsetWidth || 0) < 50 || (host.offsetHeight || 0) < 50) return null;
            return host;
        },

        resizeBlockly() {
            const ws = blockyWs();
            if (!ws || !window.Blockly) return;
            const host = this.blocklyHostReady();
            if (!host) return;
            try {
                const inj = host.querySelector(".injectionDiv");
                if (inj) {
                    inj.style.position = "absolute";
                    inj.style.left = "0";
                    inj.style.top = "0";
                    inj.style.right = "0";
                    inj.style.bottom = "0";
                    // Do not force width/height % — that skews Blockly metrics and
                    // can park the vertical scrollbar as a gray bar over the canvas.
                    inj.style.removeProperty("width");
                    inj.style.removeProperty("height");
                }
                Blockly.svgResize(ws);
                if (ws.scrollbar && typeof ws.scrollbar.resize === "function") ws.scrollbar.resize();
            } catch (e) { /* ignore */ }
        },

        observeBlocklyHost(host) {
            if (BlockyRT.resizeObserver) BlockyRT.resizeObserver.disconnect();
            if (typeof ResizeObserver !== "undefined") {
                BlockyRT.resizeObserver = new ResizeObserver(() => this.resizeBlockly());
                BlockyRT.resizeObserver.observe(host);
            }
            if (!BlockyRT.windowResize) {
                BlockyRT.windowResize = () => this.resizeBlockly();
                window.addEventListener("resize", BlockyRT.windowResize);
            }
        },

        scrollBlocklyToTopLeft() {
            const ws = blockyWs();
            if (!ws) return;
            try {
                const m = ws.getMetrics();
                if (m) ws.scroll(-m.contentLeft + 16, -m.contentTop + 16);
            } catch (e) { /* ignore */ }
        },

        toggleBlocklyFullscreen() {
            this.blocklyFullscreen = !this.blocklyFullscreen;
            requestAnimationFrame(() => requestAnimationFrame(() => this.resizeBlockly()));
        },

        getAuthHeaders() {
            const token = localStorage.getItem("wanos_jwt") || "";
            return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
        },

        isAdminToken(token) {
            try {
                return JSON.parse(atob(token.split(".")[1])).role === "admin";
            } catch (e) {
                return false;
            }
        },

        async logout() {
            try {
                await fetch("/api/auth/logout", { method: "POST", headers: this.getAuthHeaders() });
            } catch (e) { /* ignore */ }
            localStorage.removeItem("wanos_jwt");
            window.location.href = "/login.html";
        },

        isHardDeniedEntityId(eid) {
            if (!eid) return false;
            const v = String(eid);
            return (this.hardDenyEntityIds || []).includes(v);
        },

        rebuildEntityOptions(deviceMetadata, _automations) {
            const opts = [];
            for (const [idx, meta] of Object.entries(deviceMetadata || {})) {
                if (!meta || typeof meta !== "object") continue;
                const eid = meta.entity_id ? String(meta.entity_id) : "";
                if (!eid || this.isHardDeniedEntityId(eid)) continue;
                const type = meta.type ? String(meta.type) : "unknown";
                if (type === "scene") continue;
                const labelName = meta.name ? String(meta.name) : eid;
                let origin = meta.origin ? String(meta.origin) : "";
                const idxNum = Number(idx);
                if ((type === "speaker" || type === "media_player") && !origin) {
                    if (idxNum >= 60000 && idxNum < 61000) origin = "sonos";
                    else if (idxNum >= 61000 && idxNum < 62000) origin = "onkyo";
                }
                const typeLabel = this.deviceTypeLabel(type, origin, idxNum);
                opts.push({
                    eid,
                    idx: idxNum,
                    name: labelName,
                    label: labelName,
                    type,
                    origin,
                    typeLabel,
                    max_volume: meta.max_volume != null ? Number(meta.max_volume) : null,
                    // Honor Explorer soft-hide; exclusive Hidden toggle filters via visibleEntityOptions.
                    // Currently selected eids stay sticky in blocklyEntityDropdownOptions until cleared.
                    softHidden: Boolean(meta.hidden)
                });
            }
            opts.sort((a, b) => a.name.localeCompare(b.name));
            this.entityOptions = opts;
        },

        firstEntityId(role = "trigger", preferTypes = null) {
            const opts = this.blocklyEntityDropdownOptions({ role });
            const types = preferTypes
                ? (Array.isArray(preferTypes) ? preferTypes : [preferTypes])
                : null;
            if (types && types.length) {
                const hit = opts.find((o) => {
                    if (!o[1]) return false;
                    const t = blockyEntityTypeOf(o[1]);
                    return types.includes(t);
                });
                if (hit) return hit[1];
            }
            const first = opts.find((o) => o[1]);
            return first ? first[1] : "";
        },

        /** Prefer two different lights for new-rule trigger + action defaults. */
        defaultLightPair() {
            const trigOpts = this.blocklyEntityDropdownOptions({ role: "trigger" })
                .filter((o) => o[1] && (blockyEntityTypeOf(o[1]) === "light" || blockyEntityTypeOf(o[1]) === "hue"))
                .map((o) => o[1]);
            const actOpts = this.blocklyEntityDropdownOptions({ role: "action" })
                .filter((o) => o[1] && (blockyEntityTypeOf(o[1]) === "light" || blockyEntityTypeOf(o[1]) === "hue"))
                .map((o) => o[1]);
            const triggerEid = trigOpts[0]
                || this.firstEntityId("trigger", ["light", "hue"])
                || this.firstEntityId("trigger");
            const actionEid = actOpts.find((e) => e !== triggerEid)
                || actOpts[0]
                || this.firstEntityId("action", ["light", "hue"])
                || this.firstEntityId("action");
            return { triggerEid, actionEid };
        },

        /**
         * role: "trigger" | "condition" | "action"
         * Sensors/temp excluded; motion OK as trigger only; actions = actuators only.
         * Sticky: eids still selected for this role stay in the menu on the wrong Hidden
         * side (can clear, cannot re-pick once gone). Hard deny never sticky.
         */
        blocklyEntityDropdownOptions(optsIn) {
            const role = (optsIn && optsIn.role) || "action";
            const base = this.visibleEntityOptions.filter((o) => blockyEntityAllowedForRole(o, role));
            const opts = base.map((o) => [this.entityDisplayLabel(o), o.eid]);
            const seen = new Set(opts.map((o) => o[1]));
            const add = (eid) => {
                if (!eid || seen.has(eid) || this.isHardDeniedEntityId(eid)) return;
                // Keep currently selected eids in the menu (wrong Hidden side / missing meta)
                // so Blockly does not snap the field to the first catalog entry.
                seen.add(eid);
                const meta = (this.entityOptions || []).find((o) => o.eid === eid);
                if (meta) {
                    opts.push([this.entityDisplayLabel(meta), eid]);
                } else {
                    opts.push([`${eid} · (missing metadata)`, eid]);
                }
            };
            this._stickyEntityIdsForRole(role).forEach(add);
            return opts.length ? opts : [["(no entities)", ""]];
        },

        /**
         * Live workspace wins once it has entity fields for this role (deselection drops sticky).
         * Else open ruleJson (load hydrate / workspace not ready).
         * Role-scoped — action sticky does not leak into When-device.
         */
        _stickyEntityIdsForRole(role) {
            let ruleIds = [];
            try {
                const rule = JSON.parse(this.editor.ruleJson || "{}");
                ruleIds = this._ruleEntityIdsForRole(rule, role);
            } catch (e) { /* ignore */ }
            const fromWs = this._workspaceEntityIdsForRole(role);
            if (fromWs === null) return ruleIds;
            if (fromWs.length > 0) return fromWs;
            return ruleIds;
        },

        /** null = workspace not ready (caller falls back to ruleJson). */
        _workspaceEntityIdsForRole(role) {
            const ws = blockyWs();
            if (!ws) return null;
            const out = [];
            const push = (eid) => {
                if (eid) out.push(String(eid));
            };
            const blocks = ws.getAllBlocks(false);
            for (const b of blocks) {
                if (b.isInFlyout) continue;
                const t = b.type;
                if (role === "trigger") {
                    if (t === "b_trig_device" || t === "b_trig_device_edge") {
                        push(b.getFieldValue("ENTITY"));
                    }
                } else if (role === "condition") {
                    if (t === "b_condition_device") push(b.getFieldValue("ENTITY"));
                } else if (role === "action") {
                    if (t === "b_action_device") push(b.getFieldValue("ENTITY"));
                }
            }
            return out;
        },

        /** Only eids that belong in this picker role (prevents action→trigger leak). */
        _ruleEntityIdsForRole(rule, role) {
            const out = [];
            const push = (eid) => {
                if (eid) out.push(String(eid));
            };
            if (role === "trigger") {
                const t = rule.trigger;
                if (Array.isArray(t)) t.forEach((x) => x && push(x.entity_id));
                else if (t) push(t.entity_id);
                return out;
            }
            const cases = rule.cases || [];
            if (role === "condition") {
                cases.forEach((c) => (c.conditions || []).forEach((cond) => push(cond && cond.entity_id)));
                return out;
            }
            cases.forEach((c) => (c.actions || []).forEach((a) => push(a && a.entity_id)));
            return out;
        },

        blocklyEventDropdownOptions() {
            const opts = this.curatedEvents.map((e) => [blockyEventLabel(e), e]);
            const seen = new Set(this.curatedEvents);
            try {
                const rule = JSON.parse(this.editor.ruleJson || "{}");
                const addEv = (ev) => {
                    if (!ev || seen.has(ev)) return;
                    // Skip family keys — those belong on “When start or end”, not concrete events.
                    if (this.eventFamilies.includes(ev)) return;
                    seen.add(ev);
                    opts.push([blockyEventLabel(ev), ev]);
                };
                const t = rule.trigger;
                if (Array.isArray(t)) t.forEach((x) => x && addEv(x.event));
                else if (t) addEv(t.event);
            } catch (e) { /* ignore */ }
            return opts;
        },

        blocklyEventFamilyDropdownOptions() {
            return this.eventFamilies.map((f) => [this.eventFamilyLabel(f), f]);
        },

        /** Unwrap singleton trigger lists (legacy YAML often uses a 1-item list). */
        _canonicalTrigger(trigger) {
            if (Array.isArray(trigger) && trigger.length === 1) {
                return trigger[0];
            }
            return trigger;
        },

        _mkTriggerRoot(trigger, cases) {
            const t = this._canonicalTrigger(trigger);

            if (Array.isArray(t) && t.length) {
                const allDevices = t.every((x) => x && x.entity_id);
                const allEvents = t.every((x) => x && x.event && !x.entity_id);
                if (allEvents) {
                    // Multi-event OR: use event-edge blocks inside OR
                    const root = blockyMkBlock("b_trig_or", null, 16, 16);
                    const edges = t.map((edge) => blockyMkBlock("b_trig_event_edge", {
                        EVENT: edge.event
                    }));
                    blockyConnectChain(root, "EDGES", edges);
                    return root;
                }
                if (!allDevices) {
                    const first = t[0] || {};
                    if (first.event || first.entity_id) {
                        return this._mkTriggerRoot(first, cases);
                    }
                    return blockyMkBlock("b_trig_device", { ENTITY: this.firstEntityId() }, 16, 16);
                }
                const root = blockyMkBlock("b_trig_or", null, 16, 16);
                const edges = t.map((edge) => blockyMkBlock("b_trig_device_edge", {
                    ENTITY: edge.entity_id || this.firstEntityId(),
                    STATE: edge.state || "ON"
                }));
                blockyConnectChain(root, "EDGES", edges);
                return root;
            }

            if (t && t.entity_id && (t.state === "ON" || t.state === "OFF")) {
                // Legacy edge-on-trigger → device wake; put edge into cases
                if (!cases.length) {
                    cases.push({ to_state: t.state, actions: [] });
                } else if (cases.length === 1 && !cases[0].to_state) {
                    cases[0].to_state = t.state;
                }
                return blockyMkBlock("b_trig_device", {
                    ENTITY: t.entity_id
                }, 16, 16);
            }
            if (t && t.entity_id) {
                return blockyMkBlock("b_trig_device", {
                    ENTITY: t.entity_id
                }, 16, 16);
            }
            if (t && t.event && this.eventFamilies.includes(t.event)) {
                return blockyMkBlock("b_trig_family", { FAMILY: t.event }, 16, 16);
            }
            if (t && t.event) {
                return blockyMkBlock("b_trig_event", { EVENT: t.event }, 16, 16);
            }
            return blockyMkBlock("b_trig_device", {
                ENTITY: this.firstEntityId()
            }, 16, 16);
        },

        ensureBlocklyReady() {
            if (!window.Blockly) throw new Error("Blockly library not loaded.");
            BlockyRT.app = this;
            const host = this.blocklyHostReady();
            if (!host) return false;
            if (BlockyRT.ready && BlockyRT.ws && !host.querySelector(".injectionDiv")) {
                BlockyRT.ws = null;
                BlockyRT.ready = false;
                BlockyRT.schemaInjected = null;
            }
            if (BlockyRT.ready && BlockyRT.ws && BlockyRT.schemaInjected === this.blocklySchemaVersion) {
                this.resizeBlockly();
                return true;
            }
            if (BlockyRT.ready) blockyDestroyWorkspace();
            defineBlockyBlocks(Blockly, {
                entityTrigger: () => (BlockyRT.app || this).blocklyEntityDropdownOptions({ role: "trigger" }),
                entityCondition: () => (BlockyRT.app || this).blocklyEntityDropdownOptions({ role: "condition" }),
                entityAction: () => (BlockyRT.app || this).blocklyEntityDropdownOptions({ role: "action" }),
                family: () => (BlockyRT.app || this).blocklyEventFamilyDropdownOptions(),
                event: () => (BlockyRT.app || this).blocklyEventDropdownOptions()
            });
            BlockyRT.ws = Blockly.inject(host, {
                toolbox: blockyToolboxDefinition(new Set()),
                trashcan: false,
                scrollbars: true,
                move: { scrollbars: true, drag: true, wheel: true },
                zoom: { controls: true, wheel: false, startScale: 1.0 }
            });
            BlockyRT.ws.addChangeListener(blockyOnChange);
            BlockyRT.ready = true;
            BlockyRT.schemaInjected = this.blocklySchemaVersion;
            this.observeBlocklyHost(host);
            Blockly.svgResize(BlockyRT.ws);
            return true;
        },

        scheduleBlocklyLoad(attempt = 0) {
            if (!this.selectedRule || !this.showBlocklyWorkspace) return;
            requestAnimationFrame(() => {
                if (!this.selectedRule || !this.showBlocklyWorkspace) return;
                if (!this.blocklyHostReady()) {
                    if (attempt < 40) this.scheduleBlocklyLoad(attempt + 1);
                    return;
                }
                try {
                    if (!this.ensureBlocklyReady()) {
                        if (attempt < 40) this.scheduleBlocklyLoad(attempt + 1);
                        return;
                    }
                    this.loadV2IntoBlockly();
                    this.resizeBlockly();
                } catch (e) {
                    this.errorMessage = String(e && e.message ? e.message : e);
                }
            });
        },

        _conditionBlocks(list) {
            return (list || []).map((c) => {
                if (c.type === "time_of_day") {
                    return blockyMkBlock("b_condition_time", { TOD: c.is || "dark" });
                }
                return blockyMkBlock("b_condition_device", {
                    ENTITY: c.entity_id || this.firstEntityId("condition"),
                    STATE: c.is || "ON"
                });
            });
        },

        _actionBlocks(list) {
            return (list || []).map((a) => {
                if (a.event && !a.entity_id) {
                    return blockyMkBlock("b_action_event", { EVENT: a.event });
                }
                if (a.entity_id) {
                    const type = blockyEntityTypeOf(a.entity_id);
                    const isBlinds = type === "blinds" || type === "shutter";
                    const blk = blockyMkBlock("b_action_device", {
                        ENTITY: a.entity_id || this.firstEntityId("action"),
                        STATE: isBlinds ? blockyBlindsUiStateFromStored(a.state) : (a.state || "ON")
                    });
                    blockyApplyActionRich(blk, a);
                    return blk;
                }
                return blockyMkBlock("b_action_device", {
                    ENTITY: this.firstEntityId("action"),
                    STATE: "ON"
                });
            });
        },

        _caseBlocks(cases) {
            return (cases || []).map((c) => {
                const match = (
                    c.to_state === "ON" || c.to_state === "OFF"
                    || c.to_state === "OPEN" || c.to_state === "CLOSED"
                ) ? c.to_state : "NONE";
                const blk = blockyMkBlock("b_case", { MATCH: match });
                blockyConnectChain(blk, "CONDS", this._conditionBlocks(c.conditions));
                blockyConnectChain(blk, "ACTIONS", this._actionBlocks(c.actions));
                return blk;
            });
        },

        loadV2IntoBlockly() {
            if (!this.ensureBlocklyReady()) return;
            blockyCancelUniqueness();
            BlockyRT.loading = true;
            BlockyRT.suppressHueWheel = true;
            const Events = Blockly.Events;
            Events.disable();
            try {
                const ws = blockyWs();
                ws.clear();

                let rule;
                try {
                    rule = JSON.parse(this.editor.ruleJson || "{}");
                } catch (e) {
                    rule = { cases: [], trigger: {} };
                }
                const cases = rule.cases || [];
                const root = this._mkTriggerRoot(rule.trigger, cases);

                const caseBlocks = this._caseBlocks(cases.length ? cases : [{ actions: [] }]);
                if (root && caseBlocks.length) {
                    if (root.nextConnection && caseBlocks[0].previousConnection) {
                        try {
                            root.nextConnection.connect(caseBlocks[0].previousConnection);
                        } catch (e) { /* ignore */ }
                        blockyConnectNext(caseBlocks[0], caseBlocks.slice(1));
                    }
                }

                if (root && root.type === "b_trig_family" && typeof root.updateScheduleHint_ === "function") {
                    root.updateScheduleHint_(root.getFieldValue("FAMILY"));
                    blockyRefreshCaseMatchLabels(root.getNextBlock());
                } else if (root) {
                    blockyRefreshCaseMatchLabels(root.getNextBlock());
                }

                // Coerce action/condition STATE to type-valid options after load; rebuild rich shapes.
                ws.getAllBlocks(false).forEach((b) => {
                    if (b.type === "b_action_device") {
                        blockyCoerceFieldToOptions(b, "STATE", blockyActionStateOptions);
                        blockyActionUpdateRichShape(b);
                    } else if (b.type === "b_condition_device") {
                        blockyCoerceFieldToOptions(b, "STATE", blockyConditionStateOptions);
                    } else if (b.type === "b_case") {
                        blockyCoerceFieldToOptions(b, "MATCH", blockyCaseMatchOptions);
                    }
                });

                // Re-apply rich from rule JSON (authoritative) — defeats any stray shape
                // rebuild that lost _hueBri / preset during coerce.
                {
                    let caseNode = root ? root.getNextBlock() : null;
                    let ci = 0;
                    while (caseNode && caseNode.type === "b_case") {
                        const acts = (cases[ci] && cases[ci].actions) || [];
                        let ab = caseNode.getInputTargetBlock("ACTIONS");
                        let ai = 0;
                        while (ab) {
                            if (ab.type === "b_action_device") {
                                if (acts[ai] && acts[ai].entity_id) {
                                    blockyApplyActionRich(ab, acts[ai]);
                                }
                                ai += 1;
                            } else if (ab.type === "b_action_event") {
                                ai += 1;
                            }
                            ab = ab.getNextBlock();
                        }
                        ci += 1;
                        caseNode = caseNode.getNextBlock();
                    }
                }

                // Drop any rich/uniqueness work queued by field validators during mkBlock.
                if (BlockyRT.richTimer) {
                    clearTimeout(BlockyRT.richTimer);
                    BlockyRT.richTimer = null;
                }
                BlockyRT.pendingRichOpts = null;
                blockyCancelUniqueness();

                if (ws.render) ws.render();
                this.resizeBlockly();
                this.scrollBlocklyToTopLeft();
                blockyRefreshToolbox();
                requestAnimationFrame(() => {
                    this.resizeBlockly();
                    requestAnimationFrame(() => this.resizeBlockly());
                });
            } finally {
                Events.enable();
                this.markEditorClean();
                // ENTITY validators from mkBlock setField are queued as microtasks.
                // Keep loading=true until after they run so they do not clear Hue rich.
                queueMicrotask(() => {
                    BlockyRT.loading = false;
                    BlockyRT.suppressHueWheel = false;
                });
            }
        },

        _readConditions(start) {
            return blockyReadChain(start, (b) => {
                if (b.type === "b_condition_time") return { type: "time_of_day", is: b.getFieldValue("TOD") };
                return {
                    type: "device_state",
                    entity_id: b.getFieldValue("ENTITY"),
                    is: b.getFieldValue("STATE")
                };
            });
        },

        _readActions(start) {
            return blockyReadChain(start, (b) => {
                if (b.type === "b_action_event") return { event: b.getFieldValue("EVENT") };
                return blockyReadActionRich(b);
            });
        },

        applyBlocklyToV2() {
            this.ensureBlocklyReady();
            const ws = blockyWs();
            if (!ws) throw new Error("Blockly workspace not ready.");
            blockyAssertNoOrphans(ws);
            const tops = ws.getTopBlocks(true);
            const root = tops.find((b) => BLOCKY_ROOT_TRIGGERS.has(b.type));
            if (!root) throw new Error("Blockly requires one trigger block.");

            let trigger;
            let caseStart = root.getNextBlock();

            if (root.type === "b_trig_or") {
                const edges = [];
                let e = root.getInputTargetBlock("EDGES");
                while (e) {
                    if (e.type === "b_trig_device_edge") {
                        edges.push({
                            entity_id: e.getFieldValue("ENTITY"),
                            state: e.getFieldValue("STATE")
                        });
                    } else if (e.type === "b_trig_event_edge") {
                        edges.push({ event: e.getFieldValue("EVENT") });
                    } else {
                        throw new Error("OR trigger only accepts device or event edges.");
                    }
                    e = e.getNextBlock();
                }
                if (!edges.length) throw new Error("OR trigger needs at least one edge.");
                trigger = edges.length === 1 ? edges[0] : edges;
            } else if (root.type === "b_trig_device") {
                trigger = { entity_id: root.getFieldValue("ENTITY") };
            } else if (root.type === "b_trig_family") {
                trigger = { event: root.getFieldValue("FAMILY") };
            } else if (root.type === "b_trig_event") {
                trigger = { event: root.getFieldValue("EVENT") };
            } else {
                throw new Error("Unsupported trigger block. Use When device / event / start or end / When any of.");
            }

            const cases = [];
            let cur = caseStart;
            // Event / OR: MATCH is conditions-gate only — never persist to_state from a stale ON/OFF.
            const matchWritesToState = root.type === "b_trig_device" || root.type === "b_trig_family";
            while (cur && cur.type === "b_case") {
                const match = cur.getFieldValue("MATCH");
                const conds = this._readConditions(cur.getInputTargetBlock("CONDS"));
                const acts = this._readActions(cur.getInputTargetBlock("ACTIONS"));
                if (!acts.length) throw new Error("Each case needs at least one action.");
                const c = { actions: acts };
                if (matchWritesToState && (match === "ON" || match === "OFF"
                    || match === "OPEN" || match === "CLOSED")) {
                    c.to_state = match;
                }
                if (conds.length) c.conditions = conds;
                cases.push(c);
                cur = cur.getNextBlock();
            }

            if (!cases.length) throw new Error("Add at least one case with actions.");

            const sceneOk = this.triggerAllowsDashboard(trigger);
            if (!sceneOk) {
                this.editor.scene = false;
                this.editor.require_confirmation = false;
            }
            const payload = {
                id: this.editor.id || undefined,
                name: (this.editor.name || "").trim(),
                scene: sceneOk && !!this.editor.scene,
                require_confirmation: sceneOk && !!this.editor.require_confirmation,
                trigger,
                cases
            };
            if (!payload.name) throw new Error("Rule name is required.");
            this.validateNoHardDeniedEntityIds(payload);
            this.editor.ruleJson = JSON.stringify(payload, null, 2);
            return payload;
        },

        validateNoHardDeniedEntityIds(rulePayload) {
            const denied = [];
            const visit = (node, path) => {
                if (Array.isArray(node)) {
                    node.forEach((it, i) => visit(it, `${path}[${i}]`));
                    return;
                }
                if (!node || typeof node !== "object") return;
                if (node.entity_id && this.isHardDeniedEntityId(node.entity_id)) {
                    denied.push(`${path}.entity_id=${node.entity_id}`);
                }
                Object.entries(node).forEach(([k, v]) => visit(v, path ? `${path}.${k}` : k));
            };
            visit(rulePayload, "rule");
            if (denied.length) throw new Error(`Blocked by policy (hard deny): ${denied.join(", ")}`);
        },

        buildPayloadFromEditor() {
            if (this.editorMode === "blockly") {
                return this.applyBlocklyToV2();
            }
            let rule;
            try {
                rule = JSON.parse(this.editor.ruleJson || "{}");
            } catch (e) {
                throw new Error(`Rule JSON invalid (${e})`);
            }
            rule.id = this.editor.id || rule.id;
            rule.name = (this.editor.name || "").trim();
            const sceneOk = this.triggerAllowsDashboard(rule.trigger);
            rule.scene = sceneOk && !!this.editor.scene;
            rule.require_confirmation = sceneOk && !!this.editor.require_confirmation;
            if (!sceneOk) {
                this.editor.scene = false;
                this.editor.require_confirmation = false;
            }
            if (!rule.name) throw new Error("Rule name is required.");
            if (!Array.isArray(rule.cases) || !rule.cases.length) {
                throw new Error("v2 rule requires cases[].");
            }
            this.validateNoHardDeniedEntityIds(rule);
            return rule;
        },

        blankEditor() {
            // Defaults live here (New rule). Prefer light trigger + different light action.
            const { triggerEid, actionEid } = this.defaultLightPair();
            return {
                id: "",
                name: "",
                scene: false,
                require_confirmation: false,
                ruleJson: JSON.stringify({
                    trigger: { entity_id: triggerEid },
                    cases: [{ to_state: "ON", actions: [{ entity_id: actionEid, state: "ON" }] }]
                }, null, 2)
            };
        },

        newRule() {
            this.requestLeave({ type: "new" });
        },

        _doNewRule() {
            this.markEditorClean();
            this.selectedRule = { isDraft: true };
            this.editor = this.blankEditor();
            this.editorMode = "blockly";
            this.errorMessage = "";
            this.infoMessage = "";
            this.scheduleBlocklyLoad();
        },

        selectRule(rule) {
            if (!rule) return;
            if (this.selectedRule && !this.selectedRule.isDraft && rule.id && this.selectedRule.id === rule.id) {
                return;
            }
            this.requestLeave({ type: "select", rule });
        },

        _doSelectRule(rule) {
            this.markEditorClean();
            this.selectedRule = rule;
            this.errorMessage = "";
            this.infoMessage = "";
            const sceneOk = this.triggerAllowsDashboard(rule.trigger);
            this.editor = {
                id: rule.id || "",
                name: rule.name || "",
                scene: sceneOk && !!rule.scene,
                require_confirmation: sceneOk && !!rule.require_confirmation,
                ruleJson: JSON.stringify({
                    id: rule.id,
                    name: rule.name,
                    scene: sceneOk && !!rule.scene,
                    require_confirmation: sceneOk && !!rule.require_confirmation,
                    trigger: rule.trigger,
                    cases: rule.cases || []
                }, null, 2)
            };
            this.editorMode = "blockly";
            this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
            blockyCancelUniqueness();
            this.scheduleBlocklyLoad();
        },

        async refreshAll() {
            this.busy = true;
            this.errorMessage = "";
            this.infoMessage = "";
            try {
                const [stateRes, rulesRes] = await Promise.all([
                    fetch("/api/state", { headers: this.getAuthHeaders() }),
                    fetch("/api/automations", { headers: this.getAuthHeaders() })
                ]);
                if (!stateRes.ok) throw new Error(`Failed /api/state (${stateRes.status})`);
                if (!rulesRes.ok) throw new Error(`Failed /api/automations (${rulesRes.status})`);
                const state = await stateRes.json();
                const rulesPayload = await rulesRes.json();
                this.automations = (rulesPayload.automations || []).filter((r) => r && typeof r === "object");
                this.rebuildEntityOptions(state.device_metadata || {}, this.automations);
                const sys = (state && state.system) || {};
                this.huePresets = (sys.hue_presets && typeof sys.hue_presets === "object")
                    ? sys.hue_presets : {};
                this.sonosStations = (sys.sonos_stations && typeof sys.sonos_stations === "object")
                    ? sys.sonos_stations : {};
                if (this.selectedRule && this.selectedRule.id && !this.editorDirty) {
                    const fresh = this.automations.find((r) => r.id === this.selectedRule.id);
                    if (fresh) this._doSelectRule(fresh);
                }
                if (this.showBlocklyWorkspace && !this.editorDirty) this.scheduleBlocklyLoad();
            } catch (e) {
                this.errorMessage = String(e);
            } finally {
                this.busy = false;
            }
        },

        async runPostWriteRegistryCheck(opts = {}) {
            const okMsg = opts.okMsg || "Rule saved";
            const failMsg = opts.failMsg || "Saved, but registry check failed — open Admin → Debug.";
            const verifyFailMsg = opts.verifyFailMsg || "Saved, but could not verify — open Admin → Debug.";
            this.registryCheckMessage = "";
            this.registryCheckOk = null;
            try {
                const res = await fetch("/api/debug/entity-registry-check", {
                    headers: this.getAuthHeaders()
                });
                const report = await res.json().catch(() => ({}));
                if (!res.ok) {
                    this.registryCheckOk = false;
                    this.registryCheckMessage = verifyFailMsg;
                    return;
                }
                const warnN = (report.warnings || []).length;
                this.registryCheckOk = !!report.ok;
                this.registryCheckMessage = report.ok
                    ? (warnN
                        ? `${okMsg} (warnings in Admin → Debug).`
                        : okMsg)
                    : failMsg;
            } catch (e) {
                this.registryCheckOk = false;
                this.registryCheckMessage = verifyFailMsg;
            }
        },

        async saveRule() {
            this.busy = true;
            this.errorMessage = "";
            this.infoMessage = "";
            this.registryCheckMessage = "";
            this.registryCheckOk = null;
            try {
                const payload = this.buildPayloadFromEditor();
                const isUpdate = !!payload.id && this.automations.some((r) => r.id === payload.id);
                const method = isUpdate ? "PUT" : "POST";
                const res = await fetch("/api/automations", {
                    method,
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });
                const body = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(body.error || `${method} failed (${res.status})`);
                this.infoMessage = isUpdate
                    ? "Automation updated (hot-reload queued)."
                    : "Automation created (hot-reload queued).";
                this.markEditorClean();
                await this.refreshAll();
                const rid = (body.automation && body.automation.id) || payload.id;
                if (rid) {
                    const fresh = this.automations.find((r) => r.id === rid);
                    if (fresh) this._doSelectRule(fresh);
                }
                await this.runPostWriteRegistryCheck();
            } catch (e) {
                this.errorMessage = String(e);
            } finally {
                this.busy = false;
            }
        },

        async deleteRule() {
            if (!this.editor.id) {
                this.errorMessage = "No rule id to delete.";
                return;
            }
            if (!confirm(`Delete automation '${this.editor.name}'?`)) return;
            this.busy = true;
            this.errorMessage = "";
            this.infoMessage = "";
            this.registryCheckMessage = "";
            this.registryCheckOk = null;
            try {
                const res = await fetch("/api/automations", {
                    method: "DELETE",
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify({ id: this.editor.id })
                });
                const body = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(body.error || `DELETE failed (${res.status})`);
                this.infoMessage = "Automation deleted (hot-reload queued).";
                this.markEditorClean();
                await this.refreshAll();
                this._doNewRule();
                await this.runPostWriteRegistryCheck({
                    okMsg: "Rule deleted",
                    failMsg: "Deleted, but registry check failed — open Admin → Debug.",
                    verifyFailMsg: "Deleted, but could not verify — open Admin → Debug."
                });
            } catch (e) {
                this.errorMessage = String(e);
            } finally {
                this.busy = false;
            }
        },

        async init() {
            BlockyRT.app = this;
            if (wanosRedirectIfNarrow()) return;
            const token = localStorage.getItem("wanos_jwt") || "";
            if (!token) {
                window.location.href = "/login.html";
                return;
            }
            if (!this.isAdminToken(token)) {
                window.location.href = "/deviceexplorer.html";
                return;
            }
            this.isAdmin = true;
            this._onBeforeUnload = (e) => {
                if (!this.editorDirty) return;
                e.preventDefault();
                e.returnValue = "";
            };
            window.addEventListener("beforeunload", this._onBeforeUnload);
            this.$watch("editor.name", () => this.markEditorDirty());
            this.$watch("editor.scene", () => this.markEditorDirty());
            this.$watch("editor.require_confirmation", () => this.markEditorDirty());
            this.$watch("editor.ruleJson", () => this.markEditorDirty());
            await this.refreshAll();
            this.connected = true;
        }
    };
}
