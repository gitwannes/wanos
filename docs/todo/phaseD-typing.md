# ⚡ WanOS Phase D — Device typing

Switch vs light infer + override. Cross-cuts Explorer, auto-off, Planned Automations, and Blocky consumers — **not** editor chrome.

**Status:** Spec **LOCKED**.

**Related:** Shell polish → [`phaseC-shell.md`](phaseC-shell.md) (**C2** Planned Automations benefits from better `type`). Blocky → [`phaseB-blocky.md`](phaseB-blocky.md). Sequence → [`pipeline.md`](pipeline.md).

---

## 📋 D — Switch vs light 🔜 TODO

### Infer + override

| Layer | Decision |
|---|---|
| **Hue** | Always `type: light`. No override. |
| **Z-Wave / RFX binary** | Infer name tokens (`licht`, `lamp`, `led`, `spot`, …) → `light`, else `switch`. Admin **override**. |
| **`entity_id`** | **Frozen**; no rename to `light.*`. |
| **Non-Hue `light` unlocks** | Explorer filter/grouping, auto-off type row, Planned Automations type, wording. Not color. |
| **Blockly** | Non-Hue light = ON/OFF only (B10B consumers). Hue = color when ON. |
| **IDX 71/72** | Fix `recalculateIDXs` / config to match override. |

**D DoD:** Infer + override live; frozen ids; 71/72 aligned; Explorer / auto-off / timeline consistent.

---

## 🚦 Decisions locked

* Switch/light infer + override; freeze `entity_id`; fix 71/72.

## ❓ Residual Open Qs

**None.**
