# ⚡ WanOS: Visual Automation Editor (IFTTT) Architecture Guide

This document outlines the architectural roadmap for migrating WanOS automations from a developer-centric, static YAML file into a dynamic, Home Assistant-style visual "If-This-Then-That" GUI. 

Because WanOS already possesses a decoupled `AutomationEngine` and a unified `SystemState` dictionary, the engine itself requires very few changes. The core challenge is building a seamless, two-way translation bridge between the Python backend and the Alpine.js/DaisyUI frontend.

---

## 🏗️ Phase 1: The Backend API (CRUD & Hot-Reloading)
Currently, automations are parsed once from `config.yaml` and cached in memory. To support a GUI, the backend must be able to serve, modify, and save these rules on the fly without breaking the rest of your configuration file.

### 1. The Translation Endpoints
You will need dedicated FastAPI endpoints to handle the CRUD (Create, Read, Update, Delete) operations.
* `GET /api/automations`: Returns the current list of automations as a JSON array.
* `POST /api/automations`: Adds a new automation.
* `PUT /api/automations/{id}`: Updates an existing automation.
* `DELETE /api/automations/{id}`: Deletes an automation.

### 2. The `ruamel.yaml` Writer
Because `config.yaml` acts as your absolute Source of Truth, the API **cannot** just dump raw JSON back to disk (this would destroy your comments and spacing).
* You must leverage `ruamel.yaml` (which preserves comments and formatting, as used in your migration script) to surgically locate the `automations:` block in the YAML file and replace only that specific section.

### 3. The Hot-Reload Trigger
When the API successfully writes the new YAML to disk, it must instantly tell the running WanOS engine to adopt the new rules without dropping physical hardware connections.
* The API endpoint will dispatch an internal `EventType.CONFIG_RELOAD_REQUESTED` event.
* The `AutomationEngine` must intercept this, clear its internal `_config` cache, and re-parse the YAML so the new rule becomes active immediately.

---

## 🧠 Phase 2: The Frontend Data Model (Alpine.js State)
A visual rule builder is essentially a visual JSON editor. In your Alpine.js frontend, an automation is just a nested JavaScript object.

You will need an Alpine store (e.g., `x-data="automationEditor()"`) that holds a staging object for the automation currently being built or edited.

```javascript
// Example Alpine.js Data Structure for the Editor
{
  "name": "New Rule",
  "scene": false,
  "trigger": [],      // Array of trigger conditions (OR logic)
  "conditions": [],   // Array of required prerequisites (AND logic)
  "actions": []       // Array of execution payloads (Sequential logic)
}
```

* The GUI will use Alpine's `<template x-for="...">` loops to render visual "Cards" for each item in those arrays. 
* Clicking an "Add Trigger" button simply pushes a new blank trigger object `{ "idx": null, "state": "ON" }` into the `trigger` array. Alpine.js will instantly and reactively render a new UI block for it.

---

## 🎭 Phase 3: The Visual "Glue" (Semantic Dropdowns)
A GUI is useless if the user has to type raw numbers like `idx: 71003`. The interface must mask the underlying IDXs with human-readable names.

### 1. Device Lookups
* You already broadcast the `dashboard_map` and `device_metadata` over the SSE stream. The GUI dropdowns will iterate over this map. 
* When a user selects "buro licht" from a dropdown menu, the frontend visually shows the name, but binds the underlying `idx` (e.g., 71001) to the JSON payload.

### 2. Event Lookups
* You will need a hardcoded frontend dictionary mapping raw system events to friendly text. 
* Example: `SAUNA_ON` displays as "When the Sauna turns on".
* Example: `TWILIGHT_EVENING_ON_TRIGGER` displays as "When Evening Twilight begins".

---

## 🎨 Phase 4: Constructing the UI Blocks (DaisyUI)
To mimic the Home Assistant flow, the UI should be divided into three distinct vertical sections, styled with stacked DaisyUI cards.

### Block 1: WHEN (Triggers)
This defines what kicks off the automation.
* **Type Selector:** Dropdown to choose between "Device State Change" or "System Event".
* **If Device:** Dropdown for Device Name, Dropdown for Target State (`ON`, `OFF`, `SYNC`).
* **If System Event:** Dropdown of available semantic events (e.g., Sunset, Sauna active).

### Block 2: AND IF (Conditions - Optional)
This acts as the "Bouncer" to prevent the rule from firing if certain criteria aren't met.
* **Type Selector:** "Time of Day" vs. "Device State".
* **If Time:** Radio buttons for "Dark" (Nighttime) or "Light" (Daytime).
* **If Device State:** Dropdown for Device Name, Dropdown for Required State.

### Block 3: THEN DO (Actions)
This defines the actual payloads dispatched to the hardware.
* **Type Selector:** "Control Device", "Trigger Scene", or "Fire Event".
* **If Control Device:** 
  * Dropdown for Device Name. 
  * Dropdown for State (`ON`, `OFF`, `SYNC`, `SYNCOPPOSITE`). 
* **Advanced Modifiers:** A checkbox for "Force Transmission" (which silently prepends `FORCE_` to the state string in the JSON payload behind the scenes).
* **Rich Payloads (Dynamic UI):** If the selected device has `device_type: "light"` or `device_type: "speaker"`, the UI dynamically unhides optional color pickers, brightness sliders, or volume inputs specific to that hardware.

---

## 🚦 Next Architectural Decision
Before writing code, you must decide where the automation data physically lives long-term:

1. **Option A (Current):** Keep `config.yaml` as the absolute Source of Truth. This keeps everything in one file but requires surgical `ruamel.yaml` logic to update.
2. **Option B (Database):** Migrate automations entirely into the existing SQLite database. This allows for lightning-fast native JSON CRUD operations and simpler API endpoints, but splits your configuration across a YAML file and a database.