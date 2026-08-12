/**
 * Shared WanOS page shell (offline overlay, app nav, light modal).
 * Injects before Alpine (defer) binds — keep this script sync, before app.js / blocky.js.
 */
(function () {
    "use strict";

    const GEAR_SVG =
        '<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>';

    const LOGOUT_SVG =
        '<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>';

    const MENU_SVG =
        '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" /></svg>';

    const BELL_SVG =
        '<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" /></svg>';

    /** B10G: per-page deploy version (admin-only badge in titleBlock). */
    const PAGE_VERSIONS = {
        admin: 1,
        explorer: 1,
        commander: 1,
        history: 1,
        blocky: 1,
        hiddendevices: 1,
        lightingautooff: 1,
        zwave: 1
    };

    /** B10G: exact AlertManager-stored strings for reload suppress (T4 C). */
    const RELOAD_ALERT_IN_PROGRESS = [
        "Reloading all config…",
        "Reloading hue presets…",
        "Reloading timers & types…"
    ];
    const RELOAD_ALERT_COMPLETE = [
        "All config reloaded.",
        "Hue presets reloaded.",
        "Timers & types reloaded."
    ];
    const RELOAD_ALERT_FAILED_PREFIXES = [
        "All config reload failed:",
        "Hue presets reload failed:",
        "Timers & types reload failed:"
    ];

    function reloadAlertIsFailed(text) {
        return RELOAD_ALERT_FAILED_PREFIXES.some((p) => String(text || "").startsWith(p));
    }

    function computeReloadSuppressOverlay(msgs) {
        if (!Array.isArray(msgs)) return false;
        let suppress = false;
        for (const msg of msgs) {
            const text = msg && msg.message ? String(msg.message) : "";
            if (RELOAD_ALERT_IN_PROGRESS.includes(text)) suppress = true;
            if (RELOAD_ALERT_COMPLETE.includes(text) || reloadAlertIsFailed(text)) suppress = false;
        }
        return suppress;
    }

    function pageVersionBadge(page) {
        const v = PAGE_VERSIONS[page];
        if (!v) return "";
        return (
            '<span class="badge badge-outline badge-xs font-mono text-base-content/50 shrink-0 ml-1" ' +
            'x-show="isAdmin" x-cloak>v' + v + "</span>"
        );
    }

    function escAttr(s) {
        return String(s || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
    }

    function offlineOverlay({ tone = "error", message = "Establishing connection stream to WanOS backend...", extraHideExpr = "" } = {}) {
        const t = escAttr(tone);
        const msg = escAttr(message);
        const hideExtra = extraHideExpr ? " && !(" + extraHideExpr + ")" : "";
        return (
            '<div x-show="!connected && !reloadSuppressOverlay' + hideExtra + '" x-cloak ' +
            'class="fixed inset-0 z-[9999] bg-base-300/95 backdrop-blur-md flex flex-col items-center justify-center text-center px-6 transition-opacity duration-300">' +
            '<span class="loading loading-infinity w-16 text-' + t + ' mb-4"></span>' +
            '<h2 class="text-2xl font-black tracking-widest text-base-content">NOT CONNECTED</h2>' +
            '<p class="text-' + t + ' mt-2 font-mono text-sm">' + msg + "</p>" +
            "</div>"
        );
    }

    function navClick(page, url) {
        if (page === "blocky") return ' @click="navAway($event, \'' + url + '\')"';
        return "";
    }

    function joinItem({ page, id, href, label, idleHover, activeTone }) {
        const isActive = page === id;
        const base = "btn btn-sm join-item font-mono tracking-widest ";
        let cls;
        let edge = "";
        if (isActive) {
            cls = base + "font-bold text-" + activeTone + " border-" + activeTone + " bg-" + activeTone + "/10";
            if (id === "commander") edge = " nav-mid";
            if (id === "history") edge = " nav-mid"; // Automation follows for admin
            if (id === "blocky") edge = " nav-end";
            cls += edge;
        } else {
            cls = base + "text-base-content/70 hover:text-" + idleHover;
        }
        const adminOnly = (id === "blocky" || id === "history")
            && page !== "admin" && page !== id;
        const show = adminOnly ? ' x-show="isAdmin" x-cloak' : "";
        // Admin always shows Session History + Automation; blocky/history pages always show their own tab.
        return (
            '<a href="' + href + '" class="' + cls + '"' + show + navClick(page, href) + ">" +
            label + "</a>"
        );
    }

    function titleBlock(page) {
        if (page === "admin") {
            return (
                '<div class="flex items-center gap-1 min-w-0">' +
                '<div class="flex flex-col min-w-0 justify-center">' +
                '<span class="text-xs sm:text-sm md:text-xl font-black tracking-wider text-secondary truncate">⚡ WanOS // Admin</span>' +
                '<span class="text-[9px] font-mono text-base-content/40 leading-none mt-0.5 tracking-wider select-none" x-text="state.system.version_major"></span>' +
                "</div>" + pageVersionBadge("admin") +
                "</div>"
            );
        }
        if (page === "explorer") {
            return (
                '<div class="flex flex-col min-w-0 justify-center">' +
                '<div class="flex items-center gap-1 min-w-0">' +
                '<span class="text-xs sm:text-sm md:text-xl font-black tracking-wider truncate" ' +
                ':class="explorerMode === \'history\' ? \'text-accent\' : \'text-primary\'" ' +
                'x-text="explorerMode === \'history\' ? \'⚡ WanOS // Explorer · History\' : \'⚡ WanOS // Device Explorer\'"></span>' +
                pageVersionBadge("explorer") +
                "</div>" +
                '<span class="badge badge-neutral font-mono text-[9px] md:text-xs px-1.5 py-0 h-4 md:h-5 shrink-0 whitespace-nowrap" ' +
                // C10: singular Node vs plural Nodes (History badge wording unchanged)
                'x-text="explorerMode === \'history\' ? (explorerDisplayList.length + \' History\') : (explorerDisplayList.length === 1 ? \'1 Node\' : (explorerDisplayList.length + \' Nodes\'))"></span>' +
                "</div>"
            );
        }
        if (page === "commander") {
            return (
                '<div class="flex items-center gap-1 min-w-0">' +
                '<span class="text-xs sm:text-sm md:text-xl font-black tracking-wider text-secondary truncate">⚡ WanOS // WISC</span>' +
                pageVersionBadge("commander") +
                "</div>"
            );
        }
        if (page === "history") {
            return (
                '<div class="flex flex-col min-w-0 justify-center">' +
                '<div class="flex items-center gap-1 min-w-0">' +
                '<span class="text-xs sm:text-sm md:text-xl font-black tracking-wider text-accent truncate">⚡ WanOS // Session History</span>' +
                pageVersionBadge("history") +
                "</div>" +
                '<span class="badge badge-neutral font-mono text-[9px] md:text-xs px-1.5 py-0 h-4 md:h-5 shrink-0 whitespace-nowrap" ' +
                'x-text="(sessionHistoryTotal || 0) + \' Sessions\'"></span>' +
                "</div>"
            );
        }
        if (page === "blocky") {
            return (
                '<div class="flex items-center gap-1 min-w-0">' +
                '<span class="text-xs sm:text-sm md:text-xl font-black tracking-wider text-warning truncate">⚡ WanOS // Automation</span>' +
                pageVersionBadge("blocky") +
                "</div>"
            );
        }
        if (page === "hiddendevices") {
            return (
                '<div class="flex items-center gap-1 min-w-0">' +
                '<span class="text-xs sm:text-sm md:text-xl font-black tracking-wider text-secondary truncate">⚡ WanOS // Admin - Explorer Hidden Devices</span>' +
                pageVersionBadge("hiddendevices") +
                "</div>"
            );
        }
        if (page === "lightingautooff") {
            return (
                '<div class="flex items-center gap-1 min-w-0">' +
                '<span class="text-xs sm:text-sm md:text-xl font-black tracking-wider text-secondary truncate">⚡ WanOS // Admin - Timers & types</span>' +
                pageVersionBadge("lightingautooff") +
                "</div>"
            );
        }
        if (page === "zwave") {
            return (
                '<div class="flex items-center gap-1 min-w-0">' +
                '<span class="text-xs sm:text-sm md:text-xl font-black tracking-wider text-secondary truncate">⚡ WanOS // Admin - Z-Wave</span>' +
                pageVersionBadge("zwave") +
                "</div>"
            );
        }
        return "";
    }

    function mobileActive(page, id, label) {
        const bold = page === id ? ' class="font-bold text-' +
            (id === "explorer" ? "primary" : id === "commander" ? "secondary" : id === "history" ? "accent" : "warning") +
            '"' : "";
        return "<li><a href=\"/" +
            (id === "explorer" ? "deviceexplorer" : id === "commander" ? "commander" : id === "history" ? "sensorhistory" : "blocky") +
            ".html\"" + bold + navClick(page, "/" +
            (id === "explorer" ? "deviceexplorer" : id === "commander" ? "commander" : id === "history" ? "sensorhistory" : "blocky") +
            ".html") + ">" + label + "</a></li>";
    }

    function adminNotifications() {
        return (
            '<div class="dropdown dropdown-end">' +
            '<div tabindex="0" role="button" class="btn btn-ghost btn-circle relative">' +
            BELL_SVG +
            '<span class="badge badge-xs badge-error indicator-item absolute top-1 right-1" x-show="unreadAlertCount > 0" x-text="unreadAlertCount"></span>' +
            "</div>" +
            '<div tabindex="0" class="dropdown-content z-50 menu p-4 shadow-xl bg-base-200 rounded-box w-80 sm:w-96 mt-4 border border-base-300">' +
            '<div class="flex justify-between items-center mb-3 border-b border-base-300 pb-2">' +
            '<span class="font-bold text-sm uppercase text-base-400">System Notifications</span>' +
            '<button class="btn btn-xs btn-outline btn-error" @click="clearNonCriticalAlerts()" x-show="nonCriticalAlerts.length > 0">Clear All</button>' +
            "</div>" +
            '<div class="flex flex-col gap-2 max-h-[60vh] overflow-y-auto pr-1">' +
            // C2: criticals also in bell; dismissBellAlert is independent of banner dismiss
            '<template x-for="msg in bellAlerts" :key="msg.id">' +
            '<div class="bg-base-300 rounded p-3 text-sm border-l-4 shadow-sm" ' +
            ':class="msg.level === \'critical\' || msg.level === \'error\' ? \'border-error\' : (msg.level === \'success\' ? \'border-success\' : (msg.level === \'warning\' ? \'border-warning\' : \'border-info\'))">' +
            '<div class="flex justify-between items-start gap-2 mb-1">' +
            '<div class="flex-1 min-w-0 break-words leading-tight">' +
            '<span class="font-mono text-[10px] text-base-400 mr-2 whitespace-nowrap" ' +
            'x-show="msg.timestamp" x-text="msg.timestamp"></span>' +
            '<span class="font-bold" ' +
            ':class="msg.level === \'critical\' || msg.level === \'error\' ? \'text-error\' : (msg.level === \'success\' ? \'text-success\' : (msg.level === \'warning\' ? \'text-warning\' : \'text-info\'))" x-text="msg.message"></span>' +
            '</div>' +
            '<button @click="dismissBellAlert(msg.id)" class="btn btn-ghost btn-xs btn-circle text-base-400 hover:text-white shrink-0 -mt-1 -mr-1">✕</button>' +
            "</div>" +
            '<div class="flex justify-end items-center text-[10px] text-base-400 font-mono mt-2" x-show="msg.count > 1">' +
            '<span class="badge badge-neutral badge-xs font-bold" x-text="msg.count + \'x\'"></span>' +
            "</div></div></template>" +
            '<div x-show="unreadAlertCount === 0" class="text-center text-base-400 py-6 text-xs italic">No recent system events.</div>' +
            "</div></div></div>"
        );
    }

    function appNav({ page = "explorer" } = {}) {
        const headerCls = page === "admin"
            ? "navbar bg-base-100 shadow-md px-6 mb-8 flex-wrap gap-4 z-40 relative"
            : "navbar bg-base-100 shadow-md px-3 md:px-6 mb-6 flex-nowrap gap-2 items-center min-h-[3rem] relative z-[60]";

        // C2: system-command pages are gear → Admin only (no Explorer/WISC/History/Automation join)
        const systemCmd = page === "hiddendevices" || page === "lightingautooff" || page === "zwave";

        const join = systemCmd
            ? ""
            : (
                '<div class="join bg-base-200 border border-base-300">' +
                joinItem({ page, id: "explorer", href: "/deviceexplorer.html", label: "Explorer", idleHover: "primary", activeTone: "primary" }) +
                joinItem({ page, id: "commander", href: "/commander.html", label: "WISC", idleHover: "secondary", activeTone: "secondary" }) +
                joinItem({ page, id: "history", href: "/sensorhistory.html", label: "Session History", idleHover: "accent", activeTone: "accent" }) +
                joinItem({ page, id: "blocky", href: "/blocky.html", label: "Automation", idleHover: "warning", activeTone: "warning" }) +
                "</div>"
            );

        const mobile = systemCmd
            ? ""
            : (
                '<div id="mobile-nav-menu" class="dropdown dropdown-end">' +
                '<div tabindex="0" role="button" class="btn btn-ghost btn-xs text-base-content/70">' + MENU_SVG + "</div>" +
                '<ul tabindex="0" class="dropdown-content z-50 menu p-2 shadow bg-base-200 rounded-box w-52 border border-base-300 mt-4">' +
                mobileActive(page, "explorer", "Device Explorer") +
                mobileActive(page, "commander", "WISC") +
                "</ul></div>"
            );

        let leadingExtras = "";
        if (page === "admin") {
            leadingExtras = '<span class="text-[10px] font-mono text-base-content/40 select-none hidden sm:inline" x-text="state.system.version_full"></span>';
        }
        if (page === "blocky") {
            leadingExtras =
                '<button class="btn btn-ghost btn-xs text-base-content/50 hover:text-warning" @click="refreshAll()" :disabled="uiLocked" title="Refresh">' +
                '<span x-show="!refreshBusy && !busy" class="font-mono text-[10px] tracking-wider">Refresh</span>' +
                '<span x-show="refreshBusy || busy" class="loading loading-spinner loading-xs"></span></button>';
        }

        let gear = "";
        if (page !== "admin") {
            const alwaysGear = page === "blocky" || systemCmd;
            const gearClick = (page === "blocky" || systemCmd)
                ? ' @click="navAway($event, \'/admin.html\')"'
                : "";
            const gearShow = alwaysGear ? "" : ' x-show="isAdmin" x-cloak';
            gear =
                '<a href="/admin.html" class="btn btn-ghost btn-xs text-base-content/30 hover:text-primary mr-1"' +
                gearShow + ' title="Return to Admin"' + gearClick + ">" + GEAR_SVG + "</a>";
        }

        let logoutClick = '@click="logout()"';
        if (page === "blocky") {
            logoutClick = '@click="editorDirty ? requestLeave({ type: \'logout\' }) : logout()"';
        } else if (systemCmd) {
            logoutClick = '@click="dirty ? requestLeave({ type: \'logout\' }) : logout()"';
        }

        const trailing =
            '<div class="flex-none flex items-center gap-' + (page === "admin" ? "3" : "2") + '">' +
            leadingExtras + mobile + gear +
            "<button " + logoutClick + ' class="btn btn-ghost btn-xs text-base-content/30 hover:text-error" title="Logout">' +
            LOGOUT_SVG + "</button>" +
            (page === "admin" ? adminNotifications() : "") +
            "</div>";

        return (
            '<header class="' + headerCls + '">' +
            '<div class="flex-1 flex items-center gap-2 min-w-0">' + titleBlock(page) + "</div>" +
            (join
                ? '<div id="pc-nav-menu" class="justify-center flex-1 min-w-0">' + join + "</div>"
                : "") +
            trailing +
            "</header>"
        );
    }

    function lightControlModal() {
        return (
            '<dialog id="light_control_modal" class="modal modal-bottom sm:modal-middle backdrop-blur-sm z-[9999]">' +
            '<div class="modal-box border border-primary/20 bg-base-300 shadow-2xl">' +
            '<h3 class="font-bold text-lg flex items-center gap-2 uppercase tracking-widest text-primary border-b border-base-200 pb-3 mb-4">' +
            '<span x-text="activeLightName"></span></h3>' +
            '<div class="flex flex-col gap-6">' +
            "<div>" +
            '<div class="flex justify-between text-xs font-mono font-bold text-base-400 mb-2 uppercase tracking-wider">' +
            "<span>Brightness</span>" +
            '<span class="text-warning" x-text="(activeLightBri ?? 100) + \'%\'"></span></div>' +
            '<input type="range" min="1" max="100" class="range range-warning shadow-inner disabled:opacity-40 disabled:cursor-not-allowed" ' +
            ':disabled="huePresetEditMode" ' +
            ':class="huePresetEditMode ? \'opacity-40 cursor-not-allowed pointer-events-none\' : \'\'" ' +
            'x-model="activeLightBri" @input.debounce.100ms="onHueBrightnessInput()" />' +
            "</div>" +
            // C10: remove COLOR OUTPUT hex text row; keep wheel + presets only
            "<div>" +
            '<div class="relative flex flex-col items-center justify-center bg-base-200 p-4 rounded-box border border-base-300">' +
            '<div id="color-picker-container"></div>' +
            '<div x-show="huePresetEditMode" x-cloak class="absolute inset-0 rounded-box bg-base-300/35 cursor-not-allowed"></div>' +
            '</div></div>' +
            '<div class="flex items-center justify-between gap-2">' +
            '<span class="text-xs font-mono font-bold text-base-400 uppercase tracking-wider">Presets</span>' +
            '<label class="label cursor-pointer gap-2 py-0" x-show="isAdmin" x-cloak>' +
            '<span class="label-text text-[10px] font-mono">Edit</span>' +
            '<input type="checkbox" class="toggle toggle-xs toggle-warning" x-model="huePresetEditMode" />' +
            "</label></div>" +
            '<div class="max-h-40 overflow-y-auto pr-1">' +
            '<div class="grid grid-cols-2 md:grid-cols-4 gap-2">' +
            '<template x-for="(preset, key) in state.system.hue_presets" :key="key">' +
            '<div class="flex flex-col gap-1 min-w-0">' +
            '<button type="button" class="btn btn-sm btn-outline border-base-content/20 text-[10px] font-mono tracking-wide truncate shadow-sm hover:text-primary" ' +
            ':disabled="huePresetEditMode" x-text="preset.name || key" @click="applyPreset(preset, key)"></button>' +
            '<div class="flex gap-1" x-show="isAdmin && huePresetEditMode" x-cloak>' +
            '<button type="button" class="btn btn-ghost btn-xs font-mono flex-1" @click.stop="openHuePresetRenameModal(key, preset)">Rename</button>' +
            '<button type="button" class="btn btn-ghost btn-xs text-error font-mono flex-1" ' +
            ':disabled="(huePresetUsages[key] || []).length > 0" ' +
            ':title="(huePresetUsages[key] || []).length ? (\'In use: \' + huePresetUsages[key].join(\', \')) : \'Delete\'" ' +
            '@click.stop="openHuePresetDeleteModal(key, preset)">Del</button>' +
            "</div></div></template></div></div>" +
            '<button type="button" class="btn btn-sm btn-warning btn-outline font-mono text-[10px] w-full" ' +
            'x-show="isAdmin" x-cloak ' +
            ':disabled="huePresetEditMode || hueCurrentMatchesActivePreset()" ' +
            ':title="huePresetEditMode ? \'Disable Edit mode to save current colour\' : (hueCurrentMatchesActivePreset() ? \'Change colour or brightness to save a new preset\' : \'Save current colour as a new preset\')" ' +
            '@click="openHuePresetSaveModal()">Save current color as preset</button>' +
            "</div>" +
            '<div class="modal-action border-t border-base-200 pt-4 mt-6">' +
            '<form method="dialog" class="w-full flex justify-between">' +
            '<button class="btn btn-error btn-sm font-mono shadow-sm text-neutral-900" @click="injectLabHubStateChange(activeLightId, false)">TURN OFF</button>' +
            '<button class="btn btn-outline btn-sm font-mono text-base-content/70">Close</button>' +
            "</form></div></div>" +
            '<form method="dialog" class="modal-backdrop"><button>close</button></form>' +
            "</dialog>" +
            huePresetModals()
        );
    }

    function huePresetModals() {
        return (
            '<dialog id="hue_preset_delete_modal" class="modal modal-bottom sm:modal-middle backdrop-blur-sm z-[10000]">' +
            '<div class="modal-box border border-error/30 bg-base-300 shadow-2xl">' +
            '<h3 class="font-bold text-lg text-error tracking-wide">Delete preset?</h3>' +
            '<p class="py-3 text-sm text-base-content/80">' +
            'Remove preset <span class="font-mono font-bold text-warning" x-text="huePresetDeleteDisplayName"></span>? This cannot be undone.' +
            "</p>" +
            '<div class="modal-action flex-wrap gap-2">' +
            '<button type="button" class="btn btn-ghost btn-sm" @click="cancelHuePresetDeleteModal()">Cancel</button>' +
            '<button type="button" class="btn btn-error btn-sm" @click="confirmHuePresetDeleteModal()">Delete</button>' +
            "</div></div>" +
            '<form method="dialog" class="modal-backdrop"><button type="button" @click="cancelHuePresetDeleteModal()">close</button></form>' +
            "</dialog>" +
            '<dialog id="hue_preset_name_modal" class="modal modal-bottom sm:modal-middle backdrop-blur-sm z-[10000]">' +
            '<div class="modal-box border border-warning/30 bg-base-300 shadow-2xl">' +
            '<h3 class="font-bold text-lg text-warning tracking-wide" x-text="huePresetNameModalTitle"></h3>' +
            '<div class="py-3">' +
            '<label class="label py-1"><span class="label-text text-xs font-mono uppercase tracking-wider">Display name</span></label>' +
            '<input type="text" class="input input-bordered input-sm w-full font-mono" ' +
            'x-model="huePresetNameInput" @keydown.enter.prevent="confirmHuePresetNameModal()" />' +
            "</div>" +
            '<div class="modal-action flex-wrap gap-2">' +
            '<button type="button" class="btn btn-ghost btn-sm" @click="cancelHuePresetNameModal()">Cancel</button>' +
            '<button type="button" class="btn btn-warning btn-sm" @click="confirmHuePresetNameModal()">Save</button>' +
            "</div></div>" +
            '<form method="dialog" class="modal-backdrop"><button type="button" @click="cancelHuePresetNameModal()">close</button></form>' +
            "</dialog>"
        );
    }

    function mount() {
        document.querySelectorAll("[data-wanos-offline]").forEach((el) => {
            const html = offlineOverlay({
                tone: el.getAttribute("data-tone") || "error",
                message: el.getAttribute("data-message") || "Establishing connection stream to WanOS backend...",
                extraHideExpr: el.getAttribute("data-offline-suppress") || ""
            });
            el.outerHTML = html;
        });
        document.querySelectorAll("[data-wanos-nav]").forEach((el) => {
            el.outerHTML = appNav({ page: el.getAttribute("data-wanos-nav") || "explorer" });
        });
        document.querySelectorAll("[data-wanos-light-modal]").forEach((el) => {
            el.outerHTML = lightControlModal();
        });
    }

    // Script is loaded at end of <body> (after placeholders), before Alpine (defer) binds.
    mount();

    window.WanOSShell = { offlineOverlay, appNav, lightControlModal, mount, PAGE_VERSIONS };
    window.WanOSReloadAlerts = {
        IN_PROGRESS: RELOAD_ALERT_IN_PROGRESS,
        COMPLETE: RELOAD_ALERT_COMPLETE,
        FAILED_PREFIXES: RELOAD_ALERT_FAILED_PREFIXES,
        isFailed: reloadAlertIsFailed,
        computeSuppressOverlay: computeReloadSuppressOverlay
    };
})();
