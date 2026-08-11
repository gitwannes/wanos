// Phase 6B: unified Blockly canvas for schema v2 (trigger + ordered cases).
// Contextual dropdowns: only show entries valid for the current trigger / device type.
// Phase 6C: rich action authoring — Hue preset XOR custom color (iro→bri/xy), blinds open %, Sonos/Onkyo volume, Sonos station.
// Phase B10A: editor trust — Hue picker-only / type-switch rebuild / no restore-modal;
//   toolbar Delete (no trashcan); Blockly Events disable/enable paired (v13 refcount); dirty from canvas.
// Phase B10B+D: events: catalog (UUID bus) — no family triggers / SCENE_* strings;
//   per-rule enabled; unique rule names; dashboard/confirm live on the event row.
// Phase B10E: Automations Library (UE/UR/SE/SR/D + C on UE), UE form (no Blockly),
//   SE catalog view-only, SR name = SE catalog name, When/Fire user vs system,
//   fire allowlist for unused system (Sauna/IR ON/OFF always).

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

const BLOCKY_EDGE_STATES = [
    ["ON", "ON"], ["OFF", "OFF"]
];

/** Blue trigger roots — B10E adds system-event twin of When user event. */
const BLOCKY_ROOT_TRIGGERS = new Set([
    "b_trig_device", "b_trig_or", "b_trig_event", "b_trig_event_sys"
]);
/** Event-trigger roots (user or system) — same wire shape { event: uuid }. */
const BLOCKY_EVENT_TRIGGERS = new Set(["b_trig_event", "b_trig_event_sys"]);
/** Event OR-edge block types. */
const BLOCKY_EVENT_EDGES = new Set(["b_trig_event_edge", "b_trig_event_edge_sys"]);
/** Fire-event action block types. */
const BLOCKY_EVENT_ACTIONS = new Set(["b_action_event", "b_action_event_sys"]);
/** Sensor / temp-class — excluded from pickers (motion is separate: trigger OK, never action). */
const BLOCKY_SENSOR_LIKE_TYPES = new Set([
    "sensor", "temp_hum", "temp", "hum", "power", "energy", "fluid"
]);

/** Types that can appear as action targets. */
const BLOCKY_ACTUATOR_TYPES = new Set([
    "switch", "light", "blinds", "shutter", "speaker", "media_player"
]);

/**
 * Tall FieldDropdown menus (entity/event) open upward near the top of the canvas
 * and get clipped. Cap menu height (scroll inside) and clamp to the page viewport.
 */
function blockyConfigureDropdownChrome(Blockly) {
    if (!Blockly) return;
    // Fraction of viewport height — Blockly scrolls the menu when content exceeds this.
    if (Blockly.FieldDropdown) {
        Blockly.FieldDropdown.MAX_MENU_HEIGHT_VH = 0.4;
    }
    // Position/size against the full page so the popup is not bound to the workspace box.
    if (Blockly.DropDownDiv && typeof Blockly.DropDownDiv.setBoundsElement === "function") {
        Blockly.DropDownDiv.setBoundsElement(document.body);
    }
}

/**
 * Catalog UUIDs seeded for bus/dashboard but excluded from Blockly event pickers.
 * Keep in sync with core.event_catalog.NON_PICKABLE_SYSTEM_UUIDS.
 */
const BLOCKY_NON_PICKABLE_EVENT_IDS = new Set([
    "c3457c08-c26e-4ab7-8c32-76e0a746d6c3" // HUB_STATE_CHANGED — hub telemetry chatter
]);

/**
 * B10E: system UUIDs always fireable as actions even with no listening rule
 * (hardcoded Sauna/IR handlers). Keep in sync with core.event_catalog.FIRE_ALWAYS_SYSTEM_UUIDS.
 */
const BLOCKY_FIRE_ALWAYS_SYSTEM_IDS = new Set([
    "39120e7f-93e2-46ba-af70-9b6d7bf08df3", // SAUNA_ON
    "08b79199-86aa-4a1e-a29c-20ef2eb74e98", // SAUNA_OFF
    "056c3ade-659a-49e0-87f2-2c60e84ca792", // IR_ON
    "a97bba4d-78d3-4ce2-b134-fff36c2cd88c"  // IR_OFF
]);

/** localStorage key for Library sort mode (kind | name). */
const BLOCKY_LIBRARY_SORT_KEY = "blockyLibrarySortMode";

/** Resolve catalog event id → picker/UI label (wire still stores UUID). */
function blockyEventLabel(eventId) {
    const id = String(eventId || "");
    if (!id) return "(no event)";
    const rows = BlockyRT.catalogEvents || [];
    const hit = rows.find((r) => r && String(r.id) === id);
    // Catalog name only — library/dropdown badges already mark origin (no "system:" prefix).
    if (hit && hit.name) return String(hit.name);
    return id;
}

/** B10D / event-name spirit: trim + casefold for uniqueness compares. */
function blockyNormalizeNameKey(name) {
    return String(name || "").trim().toLowerCase();
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
        if (root && root.type === "b_trig_device") {
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
            // OR roots discriminate via conditions only (no to_state chrome).
            opts = [["(conditions only)", "NONE"]];
        } else if (root && BLOCKY_EVENT_TRIGGERS.has(root.type)) {
            // B10B/E: event cases keep conditions; empty = always. No ON/OFF "if" chrome.
            opts = [["(conditions only)", "NONE"]];
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

/** True when the case's root trigger is event-based (single event or OR of events). */
function blockyRootIsEventTrigger(root) {
    if (!root) return false;
    if (BLOCKY_EVENT_TRIGGERS.has(root.type)) return true;
    if (root.type !== "b_trig_or") return false;
    try {
        let e = root.getInputTargetBlock("EDGES");
        let hasEvent = false;
        let hasDevice = false;
        while (e) {
            if (BLOCKY_EVENT_EDGES.has(e.type)) hasEvent = true;
            if (e.type === "b_trig_device_edge") hasDevice = true;
            e = e.getNextBlock();
        }
        return hasEvent && !hasDevice;
    } catch (err) {
        return false;
    }
}

/**
 * B10B: hide useless "if"/MATCH chrome on event-triggered cases.
 * Keeps CONDS + ACTIONS; empty conditions = always run.
 */
function blockyCaseUpdateEventChrome(caseBlock) {
    if (!caseBlock || caseBlock.type !== "b_case") return;
    let root = null;
    try { root = caseBlock.getRootBlock && caseBlock.getRootBlock(); } catch (e) { /* ignore */ }
    const eventTrig = blockyRootIsEventTrigger(root);
    const matchField = caseBlock.getField("MATCH");
    const ifLabel = caseBlock.getField("IF_LABEL");
    try {
        if (matchField && typeof matchField.setVisible === "function") {
            matchField.setVisible(!eventTrig);
        }
        if (ifLabel && typeof ifLabel.setVisible === "function") {
            ifLabel.setVisible(!eventTrig);
        }
        if (eventTrig && matchField) {
            matchField.setValue("NONE");
        }
        if (typeof caseBlock.render === "function") caseBlock.render();
    } catch (e) { /* ignore */ }
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
            blockyCaseUpdateEventChrome(cur);
        }
        cur = cur.getNextBlock ? cur.getNextBlock() : null;
    }
}

function defineBlockyBlocks(Blockly, providers) {
    const entityTriggerDd = providers.entityTrigger || providers.entity;
    const entityConditionDd = providers.entityCondition || providers.entity;
    const entityActionDd = providers.entityAction || providers.entity;
    // B10E: separate dropdown providers for user vs system (trigger vs fire filters).
    const eventUserTrigDd = providers.eventUserTrigger || providers.event;
    const eventSysTrigDd = providers.eventSystemTrigger || providers.event;
    const eventUserFireDd = providers.eventUserFire || providers.event;
    const eventSysFireDd = providers.eventSystemFire || providers.event;

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
    // B10E: OR edges for user vs system events (same wire as root triggers).
    Blockly.Blocks.b_trig_event_edge = {
        init() {
            this.appendDummyInput()
                .appendField("When user event")
                .appendField(new Blockly.FieldDropdown(eventUserTrigDd), "EVENT");
            this.setPreviousStatement(true, "TrigEdge");
            this.setNextStatement(true, "TrigEdge");
            this.setColour(210);
            this.setTooltip("OR-list edge — user catalog event. Put inside “When any of”.");
        }
    };
    Blockly.Blocks.b_trig_event_edge_sys = {
        init() {
            this.appendDummyInput()
                .appendField("When system event")
                .appendField(new Blockly.FieldDropdown(eventSysTrigDd), "EVENT");
            this.setPreviousStatement(true, "TrigEdge");
            this.setNextStatement(true, "TrigEdge");
            this.setColour(210);
            this.setTooltip("OR-list edge — system catalog event. Put inside “When any of”.");
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
    // B10E: one block type pair — labels say user vs system; dropdowns filter by origin.
    Blockly.Blocks.b_trig_event = {
        init() {
            this.appendDummyInput()
                .appendField("When user event")
                .appendField(new Blockly.FieldDropdown(eventUserTrigDd), "EVENT");
            this.setNextStatement(true, "Case");
            this.setColour(210);
            this.setTooltip("Fires when this user catalog event UUID is emitted on the bus.");
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && (ev.type === "create" || ev.type === "move"
                || (ev.type === "change" && ev.name === "EVENT"))) {
                blockyRefreshCaseMatchLabels(this.getNextBlock());
            }
        }
    };
    Blockly.Blocks.b_trig_event_sys = {
        init() {
            this.appendDummyInput()
                .appendField("When system event")
                .appendField(new Blockly.FieldDropdown(eventSysTrigDd), "EVENT");
            this.setNextStatement(true, "Case");
            this.setColour(210);
            this.setTooltip("Fires when this system catalog event UUID is emitted on the bus.");
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && (ev.type === "create" || ev.type === "move"
                || (ev.type === "change" && ev.name === "EVENT"))) {
                blockyRefreshCaseMatchLabels(this.getNextBlock());
            }
        }
    };

    Blockly.Blocks.b_case = {
        init() {
            const block = this;
            this.appendDummyInput("MATCH_ROW")
                .appendField(new Blockly.FieldLabel("if"), "IF_LABEL")
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
                blockyCaseUpdateEventChrome(this);
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
                .appendField("Fire user event")
                .appendField(new Blockly.FieldDropdown(eventUserFireDd), "EVENT");
            this.setPreviousStatement(true, "Action");
            this.setNextStatement(true, "Action");
            this.setColour(290);
            this.setTooltip("Emit user catalog event UUID on the bus (no explorer confirm on fire-action).");
        }
    };
    Blockly.Blocks.b_action_event_sys = {
        init() {
            this.appendDummyInput()
                .appendField("Fire system event")
                .appendField(new Blockly.FieldDropdown(eventSysFireDd), "EVENT");
            this.setPreviousStatement(true, "Action");
            this.setNextStatement(true, "Action");
            this.setColour(290);
            this.setTooltip(
                "Emit system catalog event. Unused system events are excluded except Sauna/IR ON/OFF."
            );
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
                { kind: "block", type: "b_trig_event_sys" }
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
                { kind: "block", type: "b_trig_event_edge" },
                { kind: "block", type: "b_trig_event_edge_sys" }
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
                { kind: "block", type: "b_action_event" },
                { kind: "block", type: "b_action_event_sys" }
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
    /** rAF id for debounced workspace resize (grey scrollbar guard). */
    resizeRaf: null,
    /** Late setTimeout pass after flex/CSS settle. */
    resizeTimer: null,
    /** rAF id for post-edit scrollbar show/hide sync. */
    scrollSyncRaf: null,
    app: null,
    colorPicker: null,
    pendingRichOpts: null,
    richTimer: null,
    suppressHueWheel: false,
    /** Full GET /api/events rows (system + user). Pickers filter from this. */
    catalogEvents: []
};

/**
 * Strip Tailwind-ish max-size on Blockly SVGs (skews metrics → ghost scrollbars).
 */
function blockyClearSvgMetricSkews(host) {
    if (!host) return;
    host.querySelectorAll("svg").forEach((svg) => {
        svg.style.maxWidth = "none";
        svg.style.maxHeight = "none";
    });
}

/**
 * Paired h+v scrollbars never auto-hide in Blockly when content fits — the
 * background track stays as a grey bar. Hide each axis when not needed.
 * (Scrollbar.setVisible throws on paired bars; use setVisibleInternal.)
 */
function blockySyncScrollbarVisibility(ws) {
    const pair = ws && ws.scrollbar;
    if (!pair) return;
    let m;
    try {
        m = ws.getMetrics();
    } catch (e) {
        return;
    }
    if (!m) return;
    // Slack for float rounding so a 1px overflow does not keep a dead track.
    const slack = 2;
    const needH = (m.scrollWidth || m.contentWidth || 0) > (m.viewWidth || 0) + slack;
    const needV = (m.scrollHeight || m.contentHeight || 0) > (m.viewHeight || 0) + slack;
    const h = pair.hScroll;
    const v = pair.vScroll;
    try {
        if (h && typeof h.setVisibleInternal === "function") h.setVisibleInternal(needH);
        if (v && typeof v.setVisibleInternal === "function") v.setVisibleInternal(needV);
        // Corner square between bars — hide when either axis is off.
        if (pair.corner_) {
            pair.corner_.setAttribute("display", needH && needV ? "block" : "none");
        }
    } catch (e) { /* ignore */ }
}

/** Immediate resize + scrollbar sync (host must be laid out and ≥50px). */
function blockyApplyWorkspaceResize() {
    const ws = BlockyRT.ws;
    if (!ws || !window.Blockly) return;
    const host = document.getElementById("blocklyWorkspace");
    if (!host) return;
    if ((host.offsetWidth || 0) < 50 || (host.offsetHeight || 0) < 50) return;
    try {
        const inj = host.querySelector(".injectionDiv");
        if (inj) {
            inj.style.position = "absolute";
            inj.style.left = "0";
            inj.style.top = "0";
            inj.style.right = "0";
            inj.style.bottom = "0";
            // Do not force width/height % — that parks scrollbars over the canvas.
            inj.style.removeProperty("width");
            inj.style.removeProperty("height");
        }
        blockyClearSvgMetricSkews(host);
        Blockly.svgResize(ws);
        if (ws.scrollbar && typeof ws.scrollbar.resize === "function") ws.scrollbar.resize();
        blockySyncScrollbarVisibility(ws);
    } catch (e) { /* ignore */ }
}

/**
 * Debounced resize: double-rAF for Alpine/flex settle, then a short late pass.
 * Single entry point so FS alerts / park / window resize do not thrash metrics.
 */
function blockyScheduleWorkspaceResize() {
    if (BlockyRT.resizeRaf) {
        cancelAnimationFrame(BlockyRT.resizeRaf);
        BlockyRT.resizeRaf = null;
    }
    if (BlockyRT.resizeTimer) {
        clearTimeout(BlockyRT.resizeTimer);
        BlockyRT.resizeTimer = null;
    }
    BlockyRT.resizeRaf = requestAnimationFrame(() => {
        BlockyRT.resizeRaf = requestAnimationFrame(() => {
            BlockyRT.resizeRaf = null;
            blockyApplyWorkspaceResize();
            BlockyRT.resizeTimer = setTimeout(() => {
                BlockyRT.resizeTimer = null;
                blockyApplyWorkspaceResize();
            }, 50);
        });
    });
}

/** Light pass after blocks move/grow — re-show bars we hid when content now overflows. */
function blockyScheduleScrollbarSync() {
    if (BlockyRT.scrollSyncRaf) cancelAnimationFrame(BlockyRT.scrollSyncRaf);
    BlockyRT.scrollSyncRaf = requestAnimationFrame(() => {
        BlockyRT.scrollSyncRaf = null;
        const ws = BlockyRT.ws;
        if (!ws) return;
        try {
            if (ws.scrollbar && typeof ws.scrollbar.resize === "function") ws.scrollbar.resize();
            blockySyncScrollbarVisibility(ws);
        } catch (e) { /* ignore */ }
    });
}

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
        if (BLOCKY_EVENT_ACTIONS.has(t)) return `act:event:${block.getFieldValue("EVENT")}`;
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
    const isMoveAny = t === Events.BLOCK_MOVE || t === "move";
    if (!isCreate && !isChange && !isMoveRelink && !isDelete) {
        // Free XY drag still changes content bounds — keep scrollbar visibility honest.
        if (isMoveAny) blockyScheduleScrollbarSync();
        return;
    }

    // Mark dirty immediately. The uniqueness timer below can be cancelled (e.g. by
    // loadV2IntoBlockly → blockyCancelUniqueness) and must not be the only dirty path.
    if (BlockyRT.app) BlockyRT.app.markEditorDirty();
    blockyScheduleScrollbarSync();

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
    if (BlockyRT.resizeRaf) {
        cancelAnimationFrame(BlockyRT.resizeRaf);
        BlockyRT.resizeRaf = null;
    }
    if (BlockyRT.resizeTimer) {
        clearTimeout(BlockyRT.resizeTimer);
        BlockyRT.resizeTimer = null;
    }
    if (BlockyRT.scrollSyncRaf) {
        cancelAnimationFrame(BlockyRT.scrollSyncRaf);
        BlockyRT.scrollSyncRaf = null;
    }
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
        if (b.type === "b_trig_device_edge" || BLOCKY_EVENT_EDGES.has(b.type)) {
            const p = b.getParent();
            if (p && p.type === "b_trig_or") return false;
            return true; // must live inside “When any of”
        }
        if (b.type === "b_condition_device" || b.type === "b_condition_time"
            || b.type === "b_action_device" || BLOCKY_EVENT_ACTIONS.has(b.type)) {
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
        /** B10F: true ⇒ red Explorer unreachable copy; false ⇒ yellow loading. */
        backendUnreachable: false,
        busy: false,
        /** B10F: rule-save lock — busy overlay or failed (retry/dismiss). */
        ruleSaveBusy: false,
        ruleSaveFailed: false,
        isAdmin: false,
        errorMessage: "",
        infoMessage: "",
        registryCheckMessage: "",
        registryCheckOk: null,
        filterText: "",
        /** Exclusive: true ⇒ only disabled rows; false ⇒ only enabled (default).
         * Applies to UE/UR/SR/D only — SE is never disabled and ignores this toggle. */
        showDisabledOnly: false,
        /** Kind checkboxes — B10F: UE & SE default OFF; UR/SR/D default ON. */
        libraryKindFilter: { ue: false, ur: true, se: false, sr: true, d: true },
        /** 'kind' = UE→UR→SE→SR→D then name; 'name' = name only. Persisted in localStorage. */
        librarySortMode: (typeof localStorage !== "undefined"
            && localStorage.getItem(BLOCKY_LIBRARY_SORT_KEY) === "name") ? "name" : "kind",
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
        // Bump when block definitions change (B10E: user/system When+Fire twins).
        blocklySchemaVersion: 52,
        blocklyUiTick: 0,
        hardDenyEntityIds: ["switch.safety.safety_wisc_5v"],
        /**
         * B10E Library rows: UE (user events) + UR/SR/D rules + SE (all pickable
         * system catalog events, view-only). No in-memory shells — create SR via New rule.
         */
        libraryRows: [],
        /** @deprecated kept as empty alias; rebuildLibraryRows is authoritative. */
        orphanEventRows: [],
        /** Delete-blocked modal copy when DELETE /api/events returns 409. */
        eventDeleteBlockedMessage: "",
        /**
         * Disable-blocked inline usages: rule names that listen and/or fire the event.
         */
        fireRefRuleNames: [],
        /** B10F: GET /api/automations/fire-status entries keyed by event_uuid. */
        fireStatusByUuid: {},
        /** Display line above Full screen (Will fire / Has fired / Doesn't fire). */
        fireStatusLine: "",
        editor: {
            id: "",
            name: "",
            // B10B: per-rule enable (engine skips when false). Default true.
            enabled: true,
            ruleJson: "{}",
            // UE-form fields (user event — Appear on explorer / confirm / enabled).
            eventShowOnDashboard: false,
            eventRequireConfirmation: false,
            eventEnabled: true
        },

        /**
         * Left Library = UE + UR + SE + SR + D, filtered by text / kind / Show disabled/unused XOR.
         * UE/UR/SR/D: OFF = enabled only; ON = disabled only.
         * SE: OFF = used only (has listening SR); ON = unused only (no listening SR).
         */
        get filteredLibrary() {
            const q = this.filterText.trim().toLowerCase();
            const kinds = this.libraryKindFilter || {};
            const showDis = !!this.showDisabledOnly;
            // Companion SR presence — SE used/unused XOR.
            const seListeners = this._systemEventsWithListeners();
            const rows = (this.libraryRows || []).filter((r) => {
                if (!r) return false;
                const k = this.libraryKind(r);
                if (k && kinds[k] === false) return false;
                if (k === "se") {
                    // Exclusive: used view XOR unused view (SE never "disabled").
                    const sid = String(r.id || "");
                    const unused = !seListeners.has(sid);
                    if (showDis ? !unused : unused) return false;
                } else {
                    const isDis = this.libraryRowIsDisabled(r);
                    // Exclusive: enabled view XOR disabled view (UE/UR/SR/D).
                    if (showDis ? !isDis : isDis) return false;
                }
                if (!q) return true;
                const label = this.libraryRowLabel(r).toLowerCase();
                const id = String(r.id || r.systemEventId || "").toLowerCase();
                return label.includes(q) || id.includes(q);
            });
            return this._sortLibraryRows(rows);
        },

        /** Exclusive like Device Explorer: ON = only soft-hidden; OFF = only non-hidden. */
        get visibleEntityOptions() {
            return this.entityOptions.filter((opt) =>
                this.showHiddenEntities ? opt.softHidden : !opt.softHidden
            );
        },

        get showBlocklyWorkspace() {
            // UE / SE catalog rows have no Blockly canvas.
            if (this.selectedRule && (this.selectedRule.isEventRow || this.selectedRule.isSystemEventRow)) {
                return false;
            }
            return !!(this.selectedRule && this.editorMode === "blockly");
        },

        /** B10F: all Automations UI locked during rule save or until retry/dismiss. */
        get uiLocked() {
            return !!(this.ruleSaveBusy || this.ruleSaveFailed);
        },

        /** True when open UE already has a listening UR. */
        get selectedUeHasListeningUr() {
            if (!this.selectedRule || !this.selectedRule.isEventRow) return false;
            const eid = String(this.selectedRule.id || this.editor.id || "");
            if (!eid) return false;
            return this._triggerRefNamesForEvent(eid).length > 0;
        },

        /** Event id for disable locks / Show usages (UE form id, or UR rule's user-event trigger). */
        get usagesEventId() {
            if (this.selectedRule && this.selectedRule.isEventRow) {
                return String(this.editor.id || this.selectedRule.id || "");
            }
            if (this.selectedRule && this.selectedRule.isSystemEventRow) {
                return String(this.selectedRule.id || this.editor.id || "");
            }
            let trigger = this.selectedRule && this.selectedRule.trigger;
            if (!trigger) {
                try { trigger = JSON.parse(this.editor.ruleJson || "{}").trigger; }
                catch (e) { trigger = null; }
            }
            const evId = this._primaryTriggerEventId(trigger);
            if (!evId) return "";
            if (this._eventOrigin(evId) === "user") return evId;
            return "";
        },

        /**
         * True when current UE cannot be disabled: any rule *listens* (trigger)
         * OR *fires* it. Both directions block — see `_usageRuleNamesForEvent`.
         */
        get eventDisableBlocked() {
            const id = this.usagesEventId;
            if (!id || !(this.selectedRule && this.selectedRule.isEventRow)) return false;
            return this._usageRuleNamesForEvent(id).length > 0;
        },

        /** True when current UR cannot be disabled (its trigger UE is fire-referenced). */
        get ruleDisableBlocked() {
            if (!this.selectedRule || this.selectedRule.isEventRow || this.selectedRule.isSystemEventRow) {
                return false;
            }
            if (this.libraryKind(this.selectedRule) !== "ur") return false;
            const id = this.usagesEventId;
            if (!id) return false;
            return this._fireRefNamesForEvent(id).length > 0;
        },

        /** Listening SR name for the open SE catalog row (if any). */
        get selectedSeListenerName() {
            if (!this.selectedRule || !this.selectedRule.isSystemEventRow) return "";
            const eid = String(this.selectedRule.id || "");
            if (!eid) return "";
            for (const rule of this.automations || []) {
                if (!rule) continue;
                if (this._primaryTriggerEventId(rule.trigger) === eid) {
                    return String(rule.listName || rule.name || rule.id || "");
                }
            }
            return "";
        },

        toggleLibrarySortMode() {
            this.librarySortMode = this.librarySortMode === "name" ? "kind" : "name";
            try { localStorage.setItem(BLOCKY_LIBRARY_SORT_KEY, this.librarySortMode); }
            catch (e) { /* ignore */ }
        },

        libraryRowKey(row) {
            if (!row) return "nil";
            if (row.isSystemEventRow) return `se:${row.id}`;
            if (row.isEventRow) return `ue:${row.id || "draft"}`;
            return `rule:${row.id || row.name || "x"}`;
        },

        libraryRowLabel(row) {
            if (!row) return "(unnamed)";
            if (row.listName) return row.listName;
            return row.name || "(unnamed)";
        },

        /** Disabled for exclusive Show disabled/unused filter (UE/UR/SR/D). SE uses unused XOR separately. */
        libraryRowIsDisabled(row) {
            if (!row) return false;
            if (row.isSystemEventRow || this.libraryKind(row) === "se") return false;
            if (row.isEventRow) return row.enabled === false;
            return row.enabled === false;
        },

        /**
         * B10E libraryKind: ue | ur | se | sr | d.
         * UE = user event catalog; UR = user-event rule; SE = system event catalog;
         * SR = system-event rule; D = device-triggered rule.
         */
        libraryKind(rule) {
            if (!rule) return null;
            if (rule.isDraft && !rule.isEventRow && !rule.isSystemEventRow) return null;
            if (rule.libraryKind) return rule.libraryKind;
            if (rule.isEventRow) return "ue";
            if (rule.isSystemEventRow) return "se";
            const evId = this._primaryTriggerEventId(rule.trigger);
            if (evId) {
                if (this._eventOrigin(evId) === "system") return "sr";
                return "ur";
            }
            return "d";
        },

        libraryRowButtonClass(row) {
            const selected = this._isSelectedLibraryRow(row);
            const parts = ["w-full", "btn", "btn-sm", "justify-start", "text-left", "normal-case", "gap-1.5", "px-2"];
            if (selected) parts.push("btn-warning");
            else if (!(this.selectedRule && this.selectedRule.isDraft && !this.selectedRule.isEventRow
                && !this.selectedRule.isSystemEventRow)) {
                parts.push("btn-ghost");
            }
            if (this.libraryRowIsDisabled(row)) parts.push("opacity-40");
            return parts.join(" ");
        },

        _isSelectedLibraryRow(row) {
            const sel = this.selectedRule;
            if (!sel || !row) return false;
            if (sel.isSystemEventRow && row.isSystemEventRow) {
                return String(sel.id) === String(row.id);
            }
            if (sel.isEventRow && row.isEventRow) {
                if (sel.isDraft && row.isDraft) return true;
                return !!sel.id && sel.id === row.id;
            }
            if (sel.isDraft && !sel.isEventRow) return false;
            if (sel.isSystemEventRow || row.isSystemEventRow || sel.isEventRow || row.isEventRow) {
                return false;
            }
            return !!sel.id && sel.id === row.id;
        },

        _sortLibraryRows(rows) {
            const kindRank = { ue: 0, ur: 1, se: 2, sr: 3, d: 4 };
            const mode = this.librarySortMode;
            const nameKey = (r) => String(this.libraryRowLabel(r) || "").toLowerCase();
            return rows.slice().sort((a, b) => {
                if (mode !== "name") {
                    const ka = kindRank[this.libraryKind(a)] ?? 9;
                    const kb = kindRank[this.libraryKind(b)] ?? 9;
                    if (ka !== kb) return ka - kb;
                }
                return nameKey(a).localeCompare(nameKey(b), undefined, { sensitivity: "base" });
            });
        },

        _primaryTriggerEventId(trigger) {
            let t = trigger;
            if (Array.isArray(t) && t.length === 1) t = t[0];
            if (Array.isArray(t)) {
                const first = (t || []).find((x) => x && x.event && !x.entity_id);
                return first ? String(first.event) : "";
            }
            if (t && t.event && !t.entity_id) return String(t.event);
            return "";
        },

        /** Catalog origin for an event UUID (`user` | `system` | ""). */
        _eventOrigin(eventId) {
            const id = String(eventId || "");
            if (!id) return "";
            const row = (BlockyRT.catalogEvents || []).find((r) => r && String(r.id) === id);
            return row ? String(row.origin || "user") : "";
        },

        /** Catalog display name for an event UUID (empty if unknown). */
        _catalogEventName(eventId) {
            const id = String(eventId || "");
            if (!id) return "";
            const row = (BlockyRT.catalogEvents || []).find((r) => r && String(r.id) === id);
            return row && row.name ? String(row.name) : "";
        },

        /**
         * SR invariant (FE): force payload.name = companion SE catalog name.
         * Backend also overwrites on POST/PUT so YAML cannot drift.
         */
        _bindSrNameToSeCatalog(payload) {
            if (!payload || typeof payload !== "object") return payload;
            const evId = this._primaryTriggerEventId(payload.trigger);
            if (!evId || this._eventOrigin(evId) !== "system") return payload;
            const catName = this._catalogEventName(evId);
            if (catName) {
                payload.name = catName;
                this.editor.name = catName;
            }
            return payload;
        },

        /**
         * Display name for a rule in usages / blocked-delete messages.
         * SR: companion SE catalog name (never drifted YAML free-text).
         * UR: rule.name / listName.
         */
        _ruleDisplayName(rule) {
            if (!rule) return "(unnamed)";
            const evId = this._primaryTriggerEventId(rule.trigger);
            if (evId && this._eventOrigin(evId) === "system") {
                return (
                    this._catalogEventName(evId)
                    || rule.listName
                    || rule.name
                    || rule.id
                    || "(unnamed)"
                );
            }
            return String(rule.listName || rule.name || rule.id || "(unnamed)");
        },

        /** Rule names whose trigger listens to this event id (When user/system event). */
        _triggerRefNamesForEvent(eventId) {
            const id = String(eventId || "");
            if (!id) return [];
            const names = [];
            for (const rule of this.automations || []) {
                if (!rule) continue;
                if (this._primaryTriggerEventId(rule.trigger) === id) {
                    names.push(this._ruleDisplayName(rule));
                }
            }
            return names;
        },

        /** Rule names that fire this event as an action (Fire user/system event). */
        _fireRefNamesForEvent(eventId) {
            const id = String(eventId || "");
            if (!id) return [];
            const names = [];
            for (const rule of this.automations || []) {
                if (!rule) continue;
                let hit = false;
                for (const c of rule.cases || []) {
                    for (const a of c.actions || []) {
                        if (a && a.event && !a.entity_id && String(a.event) === id) {
                            hit = true;
                            break;
                        }
                    }
                    if (hit) break;
                }
                if (hit) names.push(this._ruleDisplayName(rule));
            }
            return names;
        },

        /**
         * Unique rule names that listen to OR fire this event.
         * Disable of an E is blocked when either side is non-empty: a listening U
         * must not keep a disabled catalog target, and Fire-user-event actions must
         * not target a disabled E (same product rule as backend `rule_refs_to_event`).
         */
        _usageRuleNamesForEvent(eventId) {
            const id = String(eventId || "");
            if (!id) return [];
            const seen = new Set();
            const out = [];
            for (const nm of [
                ...this._triggerRefNamesForEvent(id),
                ...this._fireRefNamesForEvent(id)
            ]) {
                if (seen.has(nm)) continue;
                seen.add(nm);
                out.push(nm);
            }
            return out;
        },

        /** Set of system event UUIDs that already have a listening rule. */
        _systemEventsWithListeners() {
            const out = new Set();
            for (const rule of this.automations || []) {
                if (!rule) continue;
                const evId = this._primaryTriggerEventId(rule.trigger);
                if (evId && this._eventOrigin(evId) === "system") out.add(evId);
            }
            return out;
        },

        onExplorerFlagChanged() {
            // Invariant: explorer OFF while confirm ON → force confirm OFF.
            if (!this.editor.eventShowOnDashboard && this.editor.eventRequireConfirmation) {
                this.editor.eventRequireConfirmation = false;
            }
            this.markEditorDirty();
        },

        showEventUsagesModal() {
            const id = this.usagesEventId;
            // UE form: listeners + fire-refs. UR disable-blocked: fire-refs of trigger only.
            if (this.selectedRule && this.selectedRule.isEventRow) {
                this.fireRefRuleNames = this._usageRuleNamesForEvent(id);
            } else {
                this.fireRefRuleNames = this._fireRefNamesForEvent(id);
            }
            const dlg = document.getElementById("event_usages_modal");
            if (dlg) dlg.showModal();
        },

        closeEventUsagesModal() {
            document.getElementById("event_usages_modal")?.close();
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
                motion: "motion"
            };
            return map[t] || t || "device";
        },

        entityDisplayLabel(opt) {
            if (opt && opt.typeLabel) return `${opt.name} · ${opt.typeLabel}`;
            return `${opt.name} · ${this.deviceTypeLabel(opt.type, opt.origin, opt.idx)}`;
        },

        /** Alpine-friendly wrapper for catalog UUID → name. */
        eventLabel(eventId) {
            return blockyEventLabel(eventId);
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
            else if (action.type === "newUserEvent") this._doNewUserEvent();
            else if (action.type === "newFromSe") this._doNewRuleFromEvent(action.eventId, "system");
            else if (action.type === "newFromUe") this._doNewRuleFromEvent(action.eventId, "user");
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
            // Debounced settle path — see blockyScheduleWorkspaceResize.
            blockyScheduleWorkspaceResize();
        },

        observeBlocklyHost(host) {
            if (BlockyRT.resizeObserver) BlockyRT.resizeObserver.disconnect();
            if (typeof ResizeObserver !== "undefined") {
                BlockyRT.resizeObserver = new ResizeObserver(() => blockyScheduleWorkspaceResize());
                BlockyRT.resizeObserver.observe(host);
            }
            if (!BlockyRT.windowResize) {
                BlockyRT.windowResize = () => blockyScheduleWorkspaceResize();
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
            blockyScheduleWorkspaceResize();
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
         * HIDDEN is exclusive (ON = soft-hidden catalog; OFF = non-hidden) + sticky current.
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
         * Live workspace wins once load is finished (deselection drops sticky).
         * During load, always use full open-rule eids — a partial workspace list
         * (blocks created one-by-one) would omit later action eids and FieldDropdown
         * would snap them to options[0] (seen as identical wrong labels when HIDDEN ON).
         * Role-scoped — action sticky does not leak into When-device.
         */
        _stickyEntityIdsForRole(role) {
            let ruleIds = [];
            try {
                const rule = JSON.parse(this.editor.ruleJson || "{}");
                ruleIds = this._ruleEntityIdsForRole(rule, role);
            } catch (e) { /* ignore */ }
            // Load path: ruleJson is complete; workspace is still being filled.
            if (BlockyRT.loading) return ruleIds;
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

        /**
         * B10E event pickers — filter by origin (user|system) and role (trigger|fire).
         * Trigger system: unused SEs only (sticky keeps current when editing SR).
         * Fire system: listeners OR FIRE_ALWAYS only.
         * Sticky: events already on the open rule stay listed (round-trip safe).
         */
        blocklyEventDropdownOptions(optsIn) {
            const originWant = (optsIn && optsIn.origin) || "";
            const role = (optsIn && optsIn.role) || "trigger";
            const catalog = BlockyRT.catalogEvents || [];
            const listeners = this._systemEventsWithListeners();
            let pickable = catalog.filter((r) => {
                if (!r || !r.id) return false;
                if (BLOCKY_NON_PICKABLE_EVENT_IDS.has(String(r.id))) return false;
                const origin = String(r.origin || "user");
                if (originWant && origin !== originWant) return false;
                if (origin === "system") {
                    const id = String(r.id);
                    if (role === "fire") {
                        // Unused system not fireable except Sauna/IR ON/OFF always.
                        return BLOCKY_FIRE_ALWAYS_SYSTEM_IDS.has(id) || listeners.has(id);
                    }
                    // New SR: only unused SEs; editing keeps current via sticky below.
                    return !listeners.has(id);
                }
                // User: enabled only (disabled stay sticky if already on rule).
                return r.enabled !== false;
            });
            const nameKey = (r) => String(r.name || r.id || "");
            pickable.sort((a, b) => nameKey(a).localeCompare(nameKey(b), undefined, { sensitivity: "base" }));
            const opts = pickable.map((r) => [blockyEventLabel(r.id), String(r.id)]);
            const seen = new Set(opts.map((o) => o[1]));
            const addSticky = (evId) => {
                const id = String(evId || "");
                if (!id || seen.has(id)) return;
                // Sticky must still match origin filter when set.
                if (originWant) {
                    const o = this._eventOrigin(id);
                    if (o && o !== originWant) return;
                }
                seen.add(id);
                opts.push([blockyEventLabel(id), id]);
            };
            try {
                const rule = JSON.parse(this.editor.ruleJson || "{}");
                const t = rule.trigger;
                if (role === "trigger") {
                    if (Array.isArray(t)) t.forEach((x) => x && addSticky(x.event));
                    else if (t) addSticky(t.event);
                } else {
                    (rule.cases || []).forEach((c) => {
                        (c.actions || []).forEach((a) => {
                            if (a && a.event && !a.entity_id) addSticky(a.event);
                        });
                    });
                }
            } catch (e) { /* ignore */ }
            // Also sticky live canvas picks during edit.
            try {
                const ws = blockyWs();
                if (ws && !BlockyRT.loading) {
                    ws.getAllBlocks(false).forEach((b) => {
                        if (b.isInFlyout) return;
                        if (role === "trigger") {
                            if (BLOCKY_EVENT_TRIGGERS.has(b.type) || BLOCKY_EVENT_EDGES.has(b.type)) {
                                addSticky(b.getFieldValue("EVENT"));
                            }
                        } else if (BLOCKY_EVENT_ACTIONS.has(b.type)) {
                            addSticky(b.getFieldValue("EVENT"));
                        }
                    });
                }
            } catch (e) { /* ignore */ }
            return opts.length ? opts : [["(no events)", ""]];
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
                    // Multi-event OR: use event-edge blocks inside OR (user vs system by catalog).
                    const root = blockyMkBlock("b_trig_or", null, 16, 16);
                    const edges = t.map((edge) => {
                        const origin = this._eventOrigin(edge.event);
                        const type = origin === "system" ? "b_trig_event_edge_sys" : "b_trig_event_edge";
                        return blockyMkBlock(type, { EVENT: edge.event });
                    });
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
            // B10B/E: trigger.event is always a catalog UUID — pick user vs system block by origin.
            if (t && t.event) {
                const origin = this._eventOrigin(t.event);
                const type = origin === "system" ? "b_trig_event_sys" : "b_trig_event";
                return blockyMkBlock(type, { EVENT: t.event }, 16, 16);
            }
            // B10F: empty New rule — no default When device (blank canvas).
            return null;
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
                eventUserTrigger: () => (BlockyRT.app || this).blocklyEventDropdownOptions({
                    origin: "user", role: "trigger"
                }),
                eventSystemTrigger: () => (BlockyRT.app || this).blocklyEventDropdownOptions({
                    origin: "system", role: "trigger"
                }),
                eventUserFire: () => (BlockyRT.app || this).blocklyEventDropdownOptions({
                    origin: "user", role: "fire"
                }),
                eventSystemFire: () => (BlockyRT.app || this).blocklyEventDropdownOptions({
                    origin: "system", role: "fire"
                })
            });
            BlockyRT.ws = Blockly.inject(host, {
                toolbox: blockyToolboxDefinition(new Set()),
                trashcan: false,
                scrollbars: true,
                move: { scrollbars: true, drag: true, wheel: true },
                zoom: { controls: true, wheel: false, startScale: 1.0 }
            });
            // After inject: dropdown chrome needs DropDownDiv on the page.
            blockyConfigureDropdownChrome(Blockly);
            BlockyRT.ws.addChangeListener(blockyOnChange);
            BlockyRT.ready = true;
            BlockyRT.schemaInjected = this.blocklySchemaVersion;
            this.observeBlocklyHost(host);
            blockyScheduleWorkspaceResize();
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
                    const origin = this._eventOrigin(a.event);
                    const type = origin === "system" ? "b_action_event_sys" : "b_action_event";
                    return blockyMkBlock(type, { EVENT: a.event });
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

                // Empty draft: no root and no cases → blank workspace (B10F).
                const caseBlocks = root
                    ? this._caseBlocks(cases.length ? cases : [{ actions: [] }])
                    : (cases.length ? this._caseBlocks(cases) : []);
                if (root && caseBlocks.length) {
                    if (root.nextConnection && caseBlocks[0].previousConnection) {
                        try {
                            root.nextConnection.connect(caseBlocks[0].previousConnection);
                        } catch (e) { /* ignore */ }
                        blockyConnectNext(caseBlocks[0], caseBlocks.slice(1));
                    }
                }

                if (root) {
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
                        blockyCaseUpdateEventChrome(b);
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
                                    // Re-assert ENTITY after full sticky catalog exists (heals
                                    // any mid-load snap if options were still incomplete).
                                    blockySafeSetField(ab, "ENTITY", acts[ai].entity_id);
                                    blockyApplyActionRich(ab, acts[ai]);
                                }
                                ai += 1;
                            } else if (BLOCKY_EVENT_ACTIONS.has(ab.type)) {
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
                // Create SR/UE→UR drafts stay dirty; normal loads clear dirty after inject.
                if (this._markDirtyAfterBlocklyLoad) {
                    this._markDirtyAfterBlocklyLoad = false;
                    this.editorDirty = true;
                    this.suppressDirtyUntil = 0;
                    this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
                } else {
                    this.markEditorClean();
                }
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
                if (BLOCKY_EVENT_ACTIONS.has(b.type)) return { event: b.getFieldValue("EVENT") };
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
                    } else if (BLOCKY_EVENT_EDGES.has(e.type)) {
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
            } else if (BLOCKY_EVENT_TRIGGERS.has(root.type)) {
                trigger = { event: root.getFieldValue("EVENT") };
            } else {
                throw new Error(
                    "Unsupported trigger block. Use When device / When user event / When system event / When any of."
                );
            }

            const cases = [];
            let cur = caseStart;
            // Device: MATCH writes to_state. Event / OR: conditions-gate only — never persist to_state.
            const matchWritesToState = root.type === "b_trig_device";
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

            // B10B: scene/require_confirmation no longer live on the rule — flags are on events:.
            const payload = {
                id: this.editor.id || undefined,
                name: (this.editor.name || "").trim(),
                enabled: this.editor.enabled !== false,
                trigger,
                cases
            };
            // SR: name always equals companion SE catalog name (before uniqueness check).
            this._bindSrNameToSeCatalog(payload);
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
            rule.enabled = this.editor.enabled !== false;
            // Strip legacy scene flags if present in hand-edited JSON.
            delete rule.scene;
            delete rule.require_confirmation;
            // SR: name always equals companion SE catalog name.
            this._bindSrNameToSeCatalog(rule);
            if (!rule.name) throw new Error("Rule name is required.");
            if (!Array.isArray(rule.cases) || !rule.cases.length) {
                throw new Error("v2 rule requires cases[].");
            }
            this.validateNoHardDeniedEntityIds(rule);
            return rule;
        },

        /** B10D: block Save when another rule has the same trim+casefold name. */
        assertUniqueRuleName(name, excludeId) {
            const needle = blockyNormalizeNameKey(name);
            if (!needle) throw new Error("Rule name is required.");
            for (const r of this.automations || []) {
                if (!r || r.isEventRow) continue;
                const rid = String(r.id || "");
                if (excludeId && rid === String(excludeId)) continue;
                if (blockyNormalizeNameKey(r.name) === needle) {
                    throw new Error(
                        `Another automation already uses the name "${(r.name || "").trim()}" `
                        + `(case-insensitive). Choose a unique name.`
                    );
                }
            }
        },

        blankEditor() {
            // B10F: New rule starts empty — no default When device / actions.
            return {
                id: "",
                name: "",
                enabled: true,
                ruleJson: JSON.stringify({
                    enabled: true,
                    trigger: {},
                    cases: []
                }, null, 2),
                eventShowOnDashboard: false,
                eventRequireConfirmation: false,
                eventEnabled: true
            };
        },

        /**
         * B10F: draft New rule with When-system/user event preselected (no POST until Save).
         */
        blankEditorForEvent(eventId, origin) {
            const eid = String(eventId || "");
            let name = "";
            if (origin === "system") {
                // SR name locked to SE catalog name.
                name = this._catalogEventName(eid)
                    || (() => {
                        const se = (this.libraryRows || []).find(
                            (r) => r && r.isSystemEventRow && String(r.id) === eid
                        );
                        return se ? String(se.name || se.listName || "") : "";
                    })();
            }
            return {
                id: "",
                name,
                enabled: true,
                ruleJson: JSON.stringify({
                    enabled: true,
                    trigger: { event: eid },
                    cases: [{ to_state: "ON", actions: [] }]
                }, null, 2),
                eventShowOnDashboard: false,
                eventRequireConfirmation: false,
                eventEnabled: true
            };
        },

        newRule() {
            this.requestLeave({ type: "new" });
        },

        newUserEvent() {
            this.requestLeave({ type: "newUserEvent" });
        },

        _doNewRule() {
            this.markEditorClean();
            this.selectedRule = { isDraft: true };
            this.editor = this.blankEditor();
            this.editorMode = "blockly";
            this.errorMessage = "";
            this.infoMessage = "";
            this.fireStatusLine = "";
            this.scheduleBlocklyLoad();
        },

        /** B10F: draft New rule with When event preselected (SE→SR or UE→UR). */
        _doNewRuleFromEvent(eventId, origin) {
            this.markEditorClean();
            this.selectedRule = { isDraft: true };
            this.editor = this.blankEditorForEvent(eventId, origin);
            this.editorMode = "blockly";
            this.errorMessage = "";
            this.infoMessage = "";
            this.fireStatusLine = "";
            // Prefill is already a change — keep dirty through Blockly load (B10F items 6/9).
            this.editorDirty = true;
            this._markDirtyAfterBlocklyLoad = true;
            this.scheduleBlocklyLoad();
        },

        /** B10F: unused SE → open New rule with When system event preselected (draft). */
        createSystemRuleForSelectedSe() {
            if (this.uiLocked) return;
            if (!this.selectedRule || !this.selectedRule.isSystemEventRow) return;
            if (this.selectedSeListenerName) return;
            const eid = String(this.selectedRule.id || "");
            if (!eid) return;
            this.requestLeave({ type: "newFromSe", eventId: eid });
        },

        /** B10F: unused UE → open New rule with When user event preselected (draft). */
        createUserRuleForSelectedUe() {
            if (this.uiLocked) return;
            if (!this.selectedRule || !this.selectedRule.isEventRow) return;
            if (this.selectedUeHasListeningUr) return;
            const eid = String(this.selectedRule.id || this.editor.id || "");
            if (!eid) return;
            this.requestLeave({ type: "newFromUe", eventId: eid });
        },

        /** B10E: draft UE form — Save → POST /api/events only (no Blockly / no rule). */
        _doNewUserEvent() {
            this.markEditorClean();
            this.selectedRule = { isDraft: true, isEventRow: true, libraryKind: "ue" };
            this.editor = {
                id: "",
                name: "",
                enabled: true,
                ruleJson: "{}",
                eventShowOnDashboard: false,
                eventRequireConfirmation: false,
                eventEnabled: true
            };
            this.editorMode = "blockly";
            this.errorMessage = "";
            this.infoMessage = "";
            this.fireRefRuleNames = [];
        },

        selectRule(rule) {
            if (!rule) return;
            if (this._isSelectedLibraryRow(rule) && !(rule.isDraft)) return;
            this.requestLeave({ type: "select", rule });
        },

        _doSelectRule(rule) {
            this.markEditorClean();
            this.selectedRule = rule;
            this.errorMessage = "";
            this.infoMessage = "";
            this.eventDeleteBlockedMessage = "";
            this.fireRefRuleNames = [];

            // UE row — catalog form only (no Blockly).
            if (rule && rule.isEventRow) {
                this.editor = {
                    id: rule.id || "",
                    name: rule.name || "",
                    enabled: true,
                    ruleJson: "{}",
                    eventShowOnDashboard: !!rule.show_on_dashboard,
                    eventRequireConfirmation: !!rule.require_confirmation,
                    eventEnabled: rule.enabled !== false
                };
                this.editorMode = "blockly";
                // Prefill usages for disable-blocked + Show usages (listeners OR fire-refs).
                this.fireRefRuleNames = this._usageRuleNamesForEvent(rule.id);
                this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
                return;
            }

            // SE row — system catalog view-only (immutable; create SR via New rule / Create button).
            if (rule && rule.isSystemEventRow) {
                this.editor = {
                    id: rule.id || "",
                    name: rule.name || "",
                    enabled: true,
                    ruleJson: "{}",
                    eventShowOnDashboard: false,
                    eventRequireConfirmation: false,
                    eventEnabled: true
                };
                this.editorMode = "blockly";
                this.fireStatusLine = "";
                this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
                return;
            }

            // SR: show SE catalog name in the locked name field (even if YAML drifted).
            const kind = this.libraryKind(rule);
            let displayName = rule.name || "";
            if (kind === "sr") {
                displayName = rule.listName
                    || this._catalogEventName(this._primaryTriggerEventId(rule.trigger))
                    || displayName;
            }

            this.editor = {
                id: rule.id || "",
                name: displayName,
                enabled: rule.enabled !== false,
                ruleJson: JSON.stringify({
                    id: rule.id,
                    name: displayName,
                    enabled: rule.enabled !== false,
                    trigger: rule.trigger,
                    cases: rule.cases || []
                }, null, 2),
                eventShowOnDashboard: false,
                eventRequireConfirmation: false,
                eventEnabled: true
            };
            this.editorMode = "blockly";
            this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
            // Prefill usages for UR whose trigger event is fire-referenced.
            if (kind === "ur") {
                const evId = this._primaryTriggerEventId(rule.trigger);
                this.fireRefRuleNames = this._fireRefNamesForEvent(evId);
            }
            this.refreshFireStatusLine();
            blockyCancelUniqueness();
            this.scheduleBlocklyLoad();
        },

        /**
         * Rebuild Library rows: all user events (UE) + rules (UR/SR/D) + all pickable
         * system catalog events (SE, view-only). Unused SE = no listening SR (not disabled).
         */
        rebuildLibraryRows() {
            const catalog = BlockyRT.catalogEvents || [];
            const rules = this.automations || [];
            const rows = [];

            // UE: every user catalog event (including those with listening UR rules).
            for (const r of catalog) {
                if (!r || String(r.origin || "user") !== "user") continue;
                rows.push({
                    id: String(r.id),
                    name: String(r.name || r.id),
                    listName: String(r.name || r.id),
                    origin: "user",
                    show_on_dashboard: !!r.show_on_dashboard,
                    require_confirmation: !!r.require_confirmation,
                    enabled: r.enabled !== false,
                    isEventRow: true,
                    libraryKind: "ue"
                });
            }

            // UR / SR / D from real automation rules.
            for (const rule of rules) {
                if (!rule || typeof rule !== "object") continue;
                const kind = (() => {
                    const evId = this._primaryTriggerEventId(rule.trigger);
                    if (evId) {
                        return this._eventOrigin(evId) === "system" ? "sr" : "ur";
                    }
                    return "d";
                })();
                if (kind === "sr") {
                    const evId = this._primaryTriggerEventId(rule.trigger);
                    const cat = catalog.find((r) => r && String(r.id) === evId);
                    // List label = SE catalog name (SR name always equals SE).
                    const catName = cat ? String(cat.name || evId) : evId;
                    rows.push(Object.assign({}, rule, {
                        libraryKind: "sr",
                        listName: catName,
                        systemEventId: evId
                    }));
                } else {
                    rows.push(Object.assign({}, rule, {
                        libraryKind: kind,
                        listName: String(rule.name || "(unnamed)")
                    }));
                }
            }

            // SE: all pickable system catalog events (view-only; not editable shells).
            for (const r of catalog) {
                if (!r || String(r.origin) !== "system") continue;
                const id = String(r.id);
                if (BLOCKY_NON_PICKABLE_EVENT_IDS.has(id)) continue;
                const catName = String(r.name || id);
                rows.push({
                    isSystemEventRow: true,
                    id,
                    name: catName,
                    listName: catName,
                    origin: "system",
                    enabled: true,
                    libraryKind: "se"
                });
            }

            this.libraryRows = rows;
            // Keep deprecated alias empty so stale UI never mixes orphan list.
            this.orphanEventRows = [];
        },

        /** @deprecated — use rebuildLibraryRows (B10E). */
        rebuildOrphanEventRows() {
            this.rebuildLibraryRows();
        },

        async refreshAll() {
            this.busy = true;
            // Keep save-failure message visible while ruleSaveFailed (B10F).
            if (!this.ruleSaveFailed) {
                this.errorMessage = "";
                this.infoMessage = "";
            }
            try {
                const [stateRes, rulesRes, eventsRes] = await Promise.all([
                    fetch("/api/state", { headers: this.getAuthHeaders() }),
                    fetch("/api/automations", { headers: this.getAuthHeaders() }),
                    fetch("/api/events", { headers: this.getAuthHeaders() })
                ]);
                if (!stateRes.ok) throw new Error(`Failed /api/state (${stateRes.status})`);
                if (!rulesRes.ok) throw new Error(`Failed /api/automations (${rulesRes.status})`);
                if (!eventsRes.ok) throw new Error(`Failed /api/events (${eventsRes.status})`);
                const state = await stateRes.json();
                const rulesPayload = await rulesRes.json();
                const eventsPayload = await eventsRes.json();
                this.automations = (rulesPayload.automations || []).filter((r) => r && typeof r === "object");
                BlockyRT.catalogEvents = Array.isArray(eventsPayload.events) ? eventsPayload.events : [];
                this.rebuildLibraryRows();
                this.rebuildEntityOptions(state.device_metadata || {}, this.automations);
                const sys = (state && state.system) || {};
                this.huePresets = (sys.hue_presets && typeof sys.hue_presets === "object")
                    ? sys.hue_presets : {};
                this.sonosStations = (sys.sonos_stations && typeof sys.sonos_stations === "object")
                    ? sys.sonos_stations : {};
                if (this.selectedRule && !this.editorDirty) {
                    if (this.selectedRule.isEventRow) {
                        const sid = String(this.selectedRule.id || this.editor.id || "");
                        const freshEv = (this.libraryRows || []).find(
                            (e) => e.isEventRow && String(e.id) === sid
                        );
                        if (freshEv) {
                            this._doSelectRule(Object.assign({}, freshEv, { isEventRow: true }));
                        } else if (!this.selectedRule.isDraft) {
                            this.selectedRule = null;
                        }
                    } else if (this.selectedRule.isSystemEventRow) {
                        const sid = String(this.selectedRule.id || this.editor.id || "");
                        const freshSe = (this.libraryRows || []).find(
                            (e) => e.isSystemEventRow && String(e.id) === sid
                        );
                        if (freshSe) this._doSelectRule(freshSe);
                        else this.selectedRule = null;
                    } else if (this.selectedRule.id) {
                        const fresh = this.automations.find((r) => r.id === this.selectedRule.id);
                        if (fresh) this._doSelectRule(fresh);
                    }
                }
                if (this.showBlocklyWorkspace && !this.editorDirty) this.scheduleBlocklyLoad();
                await this.fetchFireStatus();
                this.backendUnreachable = false;
                return true;
            } catch (e) {
                if (!this.ruleSaveFailed) this.errorMessage = String(e);
                // Network / HTTP failure while never connected ⇒ unreachable overlay.
                if (!this.connected) this.backendUnreachable = true;
                return false;
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

        /**
         * PUT /api/events for the open UE-form row (name / explorer / confirm / enabled).
         * Confirm is coerced off when Appear on explorer is off.
         */
        async persistUserEventFromEditor(eventId, opts = {}) {
            const id = String(eventId || "");
            if (!id) return null;
            const show = !!this.editor.eventShowOnDashboard;
            const body = {
                id,
                name: String(opts.name || this.editor.name || "").trim(),
                show_on_dashboard: show,
                require_confirmation: show && !!this.editor.eventRequireConfirmation,
                enabled: this.editor.eventEnabled !== false
            };
            if (!body.name) throw new Error("Event name is required.");
            if (body.enabled === false && this._usageRuleNamesForEvent(id).length) {
                throw new Error(
                    "Cannot disable this event — rules still listen to or fire it. See Show usages."
                );
            }
            const res = await fetch("/api/events", {
                method: "PUT",
                headers: this.getAuthHeaders(),
                body: JSON.stringify(body)
            });
            const resp = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(resp.error || `PUT /api/events failed (${res.status})`);
            return resp.event || body;
        },

        /** POST a new user event from E form (editor.name). */
        async createUserEventFromEditor() {
            const name = String(this.editor.name || "").trim();
            if (!name) throw new Error("New user event requires a name.");
            const show = !!this.editor.eventShowOnDashboard;
            const body = {
                name,
                show_on_dashboard: show,
                require_confirmation: show && !!this.editor.eventRequireConfirmation,
                enabled: this.editor.eventEnabled !== false
            };
            const res = await fetch("/api/events", {
                method: "POST",
                headers: this.getAuthHeaders(),
                body: JSON.stringify(body)
            });
            const resp = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(resp.error || `POST /api/events failed (${res.status})`);
            return resp.event;
        },

        /**
         * B10E: one listening rule max per system event UUID.
         * Throws if save would create a second listener.
         */
        assertOneSystemListener(payload) {
            const evId = this._primaryTriggerEventId(payload && payload.trigger);
            if (!evId || this._eventOrigin(evId) !== "system") return;
            const excludeId = payload && payload.id ? String(payload.id) : "";
            for (const r of this.automations || []) {
                if (!r) continue;
                if (excludeId && String(r.id) === excludeId) continue;
                if (this._primaryTriggerEventId(r.trigger) === evId) {
                    const nm = (r.name || r.id || "").trim();
                    throw new Error(
                        `Only one rule may listen to this system event`
                        + (nm ? ` (already: "${nm}")` : "")
                        + ". Edit the existing SR row instead."
                    );
                }
            }
        },

        async saveRule() {
            // SE catalog: immutable — no Save that edits the system event.
            if (this.selectedRule && this.selectedRule.isSystemEventRow) {
                this.errorMessage = "System events are catalog-only (view-only). "
                    + "Create a system rule via New rule → When system event.";
                return;
            }

            // UE row (user event): POST create or PUT update — no automation rule.
            if (this.selectedRule && this.selectedRule.isEventRow) {
                this.busy = true;
                this.errorMessage = "";
                this.infoMessage = "";
                try {
                    const isDraft = !!this.selectedRule.isDraft || !this.editor.id;
                    if (isDraft) {
                        const created = await this.createUserEventFromEditor();
                        this.infoMessage = "User event created (hot-reload queued).";
                        this.markEditorClean();
                        await this.refreshAll();
                        if (created && created.id) {
                            const row = (this.libraryRows || []).find(
                                (e) => e.isEventRow && String(e.id) === String(created.id)
                            );
                            if (row) this._doSelectRule(row);
                        }
                    } else {
                        // Coerce confirm when explorer off before PUT
                        if (!this.editor.eventShowOnDashboard) {
                            this.editor.eventRequireConfirmation = false;
                        }
                        if (this.editor.eventEnabled === false
                            && this._usageRuleNamesForEvent(this.editor.id).length) {
                            throw new Error(
                                "Cannot disable this event — rules still listen to or fire it. See usages listed below."
                            );
                        }
                        await this.persistUserEventFromEditor(this.editor.id, { name: this.editor.name });
                        this.infoMessage = "Event updated (hot-reload queued).";
                        this.markEditorClean();
                        await this.refreshAll();
                    }
                } catch (e) {
                    this.errorMessage = String(e);
                } finally {
                    this.busy = false;
                }
                return;
            }

            this.busy = true;
            this.ruleSaveBusy = true;
            this.ruleSaveFailed = false;
            this.errorMessage = "";
            this.infoMessage = "";
            this.registryCheckMessage = "";
            this.registryCheckOk = null;
            try {
                if (this.ruleDisableBlocked && this.editor.enabled === false) {
                    throw new Error(
                        "Cannot disable this rule — its user event is fired by other rules. See usages listed below."
                    );
                }
                const payload = this.buildPayloadFromEditor();
                this.assertUniqueRuleName(payload.name, payload.id);
                this.assertOneSystemListener(payload);

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
                this.ruleSaveBusy = false;
                this.ruleSaveFailed = false;
                await this.refreshAll();
                const savedId = (body.automation && body.automation.id) || payload.id;
                if (savedId) {
                    const fresh = (this.libraryRows || []).find((r) =>
                        r && !r.isEventRow && !r.isSystemEventRow && r.id === savedId
                    ) || this.automations.find((r) => r.id === savedId);
                    if (fresh) this._doSelectRule(fresh);
                }
                await this.runPostWriteRegistryCheck({
                    okMsg: isUpdate ? "Rule updated" : "Rule created",
                    failMsg: "Saved, but registry check failed — open Admin → Debug."
                });
            } catch (e) {
                this.errorMessage = String(e);
                this.ruleSaveBusy = false;
                this.ruleSaveFailed = true;
            } finally {
                this.busy = false;
            }
        },

        /** B10F: re-attempt the failed rule save. */
        async retryRuleSave() {
            if (!this.ruleSaveFailed) return;
            this.ruleSaveFailed = false;
            await this.saveRule();
        },

        /** B10F: unlock UI after failed rule save; keep editor edits. */
        dismissRuleSaveFailure() {
            this.ruleSaveFailed = false;
            this.ruleSaveBusy = false;
            this.busy = false;
        },

        /**
         * B10F: ↑/↓ changes selection in the currently filtered Library list (no wrap).
         * Bound only on the Library list (not also on main — that double-fired via bubble).
         */
        onLibraryKeydown(ev) {
            if (this.uiLocked) return;
            if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
            const rows = this.filteredLibrary || [];
            if (!rows.length) return;
            // Ignore when typing in inputs (except the library list container itself).
            const tag = (ev.target && ev.target.tagName) || "";
            if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
            ev.preventDefault();
            ev.stopPropagation();
            let idx = -1;
            if (this.selectedRule) {
                const key = this.libraryRowKey(this.selectedRule);
                idx = rows.findIndex((r) => this.libraryRowKey(r) === key);
            }
            if (ev.key === "ArrowDown") {
                if (idx < 0) idx = 0;
                else if (idx < rows.length - 1) idx += 1;
                // else stop at end (no wrap)
            } else {
                if (idx < 0) idx = 0;
                else if (idx > 0) idx -= 1;
                // else stop at start (no wrap)
            }
            const next = rows[idx];
            if (!next) return;
            this.selectRule(next);
            // Keep the selected row visible inside the overflow list.
            const scrollKey = this.libraryRowKey(next);
            this.$nextTick(() => {
                const el = document.querySelector(
                    `[data-library-row-key="${CSS.escape(scrollKey)}"]`
                );
                if (el && typeof el.scrollIntoView === "function") {
                    el.scrollIntoView({ block: "nearest", inline: "nearest" });
                }
            });
        },

        /** Fetch fire-status map; refresh line for the open SR. */
        async fetchFireStatus() {
            try {
                const res = await fetch("/api/automations/fire-status", {
                    headers: this.getAuthHeaders()
                });
                if (!res.ok) return;
                const body = await res.json().catch(() => ({}));
                const map = {};
                for (const e of (body.entries || [])) {
                    if (e && e.event_uuid) map[String(e.event_uuid)] = e;
                }
                this.fireStatusByUuid = map;
                this.refreshFireStatusLine();
            } catch (e) {
                /* ignore — status line optional */
            }
        },

        /** B10F: status copy right above Full screen for in-scope SR When triggers. */
        refreshFireStatusLine() {
            this.fireStatusLine = "";
            if (!this.selectedRule || this.selectedRule.isEventRow || this.selectedRule.isSystemEventRow) {
                return;
            }
            let trigger = this.selectedRule.trigger;
            if (!trigger) {
                try { trigger = JSON.parse(this.editor.ruleJson || "{}").trigger; }
                catch (e) { trigger = null; }
            }
            const evId = this._primaryTriggerEventId(trigger);
            if (!evId || this._eventOrigin(evId) !== "system") return;
            const entry = this.fireStatusByUuid[String(evId)];
            if (!entry) return;
            const st = entry.state;
            if (st === "not_armed") return;
            if (st === "doesnt_fire_today") {
                this.fireStatusLine = "Doesn't fire today";
                return;
            }
            const hhmm = entry.at_hhmm || "";
            if (st === "will_fire" && hhmm) {
                this.fireStatusLine = `Will fire at ${hhmm}`;
                return;
            }
            if (st === "has_fired" && hhmm) {
                this.fireStatusLine = `Has fired at ${hhmm}`;
            }
        },

        async deleteRule() {
            // UE delete — DELETE /api/events with confirm; 409 → modal.
            if (this.selectedRule && this.selectedRule.isEventRow) {
                await this.deleteSelectedEvent();
                return;
            }
            if (this.selectedRule && this.selectedRule.isSystemEventRow) {
                this.errorMessage = "System events cannot be deleted (catalog seeds).";
                return;
            }
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

        /** Delete unused user event (orphan row). API guards block in-use / dashboard / system. */
        async deleteSelectedEvent() {
            const id = this.editor.id;
            if (!id) {
                this.errorMessage = "No event id to delete.";
                return;
            }
            if (!confirm(`Delete user event '${this.editor.name || id}'? This cannot be undone.`)) return;
            this.busy = true;
            this.errorMessage = "";
            this.infoMessage = "";
            this.eventDeleteBlockedMessage = "";
            try {
                const res = await fetch("/api/events", {
                    method: "DELETE",
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify({ id })
                });
                const body = await res.json().catch(() => ({}));
                if (!res.ok) {
                    const msg = body.error || `DELETE /api/events failed (${res.status})`;
                    if (res.status === 409 || res.status === 400) {
                        this.eventDeleteBlockedMessage = msg;
                        const dlg = document.getElementById("event_delete_blocked_modal");
                        if (dlg) dlg.showModal();
                        else this.errorMessage = msg;
                        return;
                    }
                    throw new Error(msg);
                }
                this.infoMessage = "Event deleted (hot-reload queued).";
                this.markEditorClean();
                await this.refreshAll();
                this.selectedRule = null;
                this.editor = {
                    id: "",
                    name: "",
                    enabled: true,
                    ruleJson: "{}",
                    eventShowOnDashboard: false,
                    eventRequireConfirmation: false,
                    eventEnabled: true
                };
            } catch (e) {
                this.errorMessage = String(e);
            } finally {
                this.busy = false;
            }
        },

        closeEventDeleteBlockedModal() {
            this.eventDeleteBlockedMessage = "";
            document.getElementById("event_delete_blocked_modal")?.close();
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
            this.$watch("editor.enabled", () => this.markEditorDirty());
            this.$watch("editor.eventShowOnDashboard", () => this.markEditorDirty());
            this.$watch("editor.eventRequireConfirmation", () => this.markEditorDirty());
            this.$watch("editor.eventEnabled", () => this.markEditorDirty());
            this.$watch("editor.ruleJson", () => this.markEditorDirty());
            // Yellow "Loading automation editor..." while connected===false && !backendUnreachable.
            const ok = await this.refreshAll();
            if (ok) {
                this.backendUnreachable = false;
                this.connected = true;
            } else {
                // Red Explorer-style unreachable copy; stay on overlay.
                this.backendUnreachable = true;
                this.connected = false;
            }
        }
    };
}
