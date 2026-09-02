# --- file: logic/element_power_store.py ---
"""Singleton element W @ 100% mod in sauna_sessions.db (C32 power model)."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

# Bootstrap defaults (former config.yaml effective_watts_*; used once on empty DB).
BOOTSTRAP_W_U: float = 3500.0
BOOTSTRAP_W_V: float = 3500.0
BOOTSTRAP_W_W: float = 2000.0
BOOTSTRAP_W_IR: float = 525.0

SAUNA_AUDIT_COLS: Tuple[str, ...] = (
    "audit_baseline_w_u", "audit_measured_w_u", "audit_new_w_u",
    "audit_baseline_w_v", "audit_measured_w_v", "audit_new_w_v",
    "audit_baseline_w_w", "audit_measured_w_w", "audit_new_w_w",
)
IR_AUDIT_COLS: Tuple[str, ...] = (
    "audit_baseline_w_ir", "audit_measured_w_ir", "audit_new_w_ir",
)

# Extra singleton columns (ALTER when missing).
ELEMENT_POWER_EXTRA_COLS: Tuple[Tuple[str, str], ...] = (
    ("learn_count_sauna", "INTEGER NOT NULL DEFAULT 0"),
    ("learn_count_ir", "INTEGER NOT NULL DEFAULT 0"),
    ("last_learn_sauna_status", "TEXT"),
    ("last_learn_sauna_detail", "TEXT"),
    ("last_learn_sauna_at", "INTEGER"),
    ("last_learn_ir_status", "TEXT"),
    ("last_learn_ir_measured_w", "REAL"),
    ("last_learn_ir_at", "INTEGER"),
)


@dataclass
class ElementPowerRow:
    w_u: float
    w_v: float
    w_w: float
    w_ir: float
    updated_at: Optional[int] = None
    source: str = "bootstrap"
    learn_count: int = 0  # legacy mirror = sauna + ir (compat)
    learn_count_sauna: int = 0
    learn_count_ir: int = 0
    last_learn_sauna_status: Optional[str] = None
    last_learn_sauna_detail: Optional[str] = None
    last_learn_sauna_at: Optional[int] = None
    last_learn_ir_status: Optional[str] = None
    last_learn_ir_measured_w: Optional[float] = None
    last_learn_ir_at: Optional[int] = None


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create element_power_w, migrate audit cols + learn split / last-learn fields."""
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS element_power_w (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            w_u REAL NOT NULL,
            w_v REAL NOT NULL,
            w_w REAL NOT NULL,
            w_ir REAL NOT NULL,
            updated_at INTEGER,
            source TEXT NOT NULL DEFAULT 'bootstrap',
            learn_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    c.execute("PRAGMA table_info(element_power_w)")
    existing_ep = {row[1] for row in c.fetchall()}
    for col, decl in ELEMENT_POWER_EXTRA_COLS:
        if col not in existing_ep:
            c.execute(f"ALTER TABLE element_power_w ADD COLUMN {col} {decl}")

    # One-time: move legacy learn_count into sauna when split cols are still zero.
    c.execute(
        """
        SELECT learn_count,
               COALESCE(learn_count_sauna, 0),
               COALESCE(learn_count_ir, 0)
        FROM element_power_w WHERE id = 1
        """
    )
    mig = c.fetchone()
    if mig is not None:
        legacy, sauna_n, ir_n = int(mig[0] or 0), int(mig[1] or 0), int(mig[2] or 0)
        if legacy > 0 and sauna_n == 0 and ir_n == 0:
            c.execute(
                "UPDATE element_power_w SET learn_count_sauna = ? WHERE id = 1",
                (legacy,),
            )

    for table, cols in (
        ("sauna_sessions", SAUNA_AUDIT_COLS),
        ("ir_sessions", IR_AUDIT_COLS),
    ):
        c.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in c.fetchall()}
        for col in cols:
            if col not in existing:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col} REAL")
    conn.commit()


def _row_from_db(row: tuple) -> ElementPowerRow:
    """Map SELECT * order from _select_sql into ElementPowerRow."""
    learn_sauna = int(row[7] or 0)
    learn_ir = int(row[8] or 0)
    legacy = int(row[6] or 0)
    if learn_sauna == 0 and learn_ir == 0 and legacy > 0:
        learn_sauna = legacy
    return ElementPowerRow(
        w_u=float(row[0]),
        w_v=float(row[1]),
        w_w=float(row[2]),
        w_ir=float(row[3]),
        updated_at=row[4],
        source=str(row[5] or "bootstrap"),
        learn_count=learn_sauna + learn_ir,
        learn_count_sauna=learn_sauna,
        learn_count_ir=learn_ir,
        last_learn_sauna_status=row[9],
        last_learn_sauna_detail=row[10],
        last_learn_sauna_at=row[11],
        last_learn_ir_status=row[12],
        last_learn_ir_measured_w=float(row[13]) if row[13] is not None else None,
        last_learn_ir_at=row[14],
    )


_SELECT_SQL = """
SELECT w_u, w_v, w_w, w_ir, updated_at, source, learn_count,
       learn_count_sauna, learn_count_ir,
       last_learn_sauna_status, last_learn_sauna_detail, last_learn_sauna_at,
       last_learn_ir_status, last_learn_ir_measured_w, last_learn_ir_at
FROM element_power_w WHERE id = 1
"""


def bootstrap_if_empty(conn: sqlite3.Connection) -> ElementPowerRow:
    """Seed singleton row when missing."""
    ensure_schema(conn)
    c = conn.cursor()
    c.execute(_SELECT_SQL)
    row = c.fetchone()
    if row is not None:
        return _row_from_db(row)
    now = int(time.time())
    c.execute(
        """
        INSERT INTO element_power_w (
            id, w_u, w_v, w_w, w_ir, updated_at, source, learn_count,
            learn_count_sauna, learn_count_ir
        ) VALUES (1, ?, ?, ?, ?, ?, 'bootstrap', 0, 0, 0)
        """,
        (BOOTSTRAP_W_U, BOOTSTRAP_W_V, BOOTSTRAP_W_W, BOOTSTRAP_W_IR, now),
    )
    conn.commit()
    return ElementPowerRow(
        w_u=BOOTSTRAP_W_U, w_v=BOOTSTRAP_W_V, w_w=BOOTSTRAP_W_W, w_ir=BOOTSTRAP_W_IR,
        updated_at=now, source="bootstrap", learn_count=0,
        learn_count_sauna=0, learn_count_ir=0,
    )


def load_row(db_path: str) -> ElementPowerRow:
    conn = sqlite3.connect(db_path)
    try:
        return bootstrap_if_empty(conn)
    finally:
        conn.close()


def save_row(db_path: str, row: ElementPowerRow) -> None:
    conn = sqlite3.connect(db_path)
    try:
        ensure_schema(conn)
        c = conn.cursor()
        # Keep legacy learn_count as sum for any old readers.
        legacy = int(row.learn_count_sauna or 0) + int(row.learn_count_ir or 0)
        c.execute(
            """
            UPDATE element_power_w SET
                w_u = ?, w_v = ?, w_w = ?, w_ir = ?,
                updated_at = ?, source = ?, learn_count = ?,
                learn_count_sauna = ?, learn_count_ir = ?,
                last_learn_sauna_status = ?, last_learn_sauna_detail = ?, last_learn_sauna_at = ?,
                last_learn_ir_status = ?, last_learn_ir_measured_w = ?, last_learn_ir_at = ?
            WHERE id = 1
            """,
            (
                row.w_u, row.w_v, row.w_w, row.w_ir,
                row.updated_at, row.source, legacy,
                row.learn_count_sauna, row.learn_count_ir,
                row.last_learn_sauna_status, row.last_learn_sauna_detail, row.last_learn_sauna_at,
                row.last_learn_ir_status, row.last_learn_ir_measured_w, row.last_learn_ir_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def count_sessions(db_path: str) -> Dict[str, int]:
    """Return recorded session counts for Admin."""
    conn = sqlite3.connect(db_path)
    try:
        ensure_schema(conn)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM sauna_sessions")
        n_sauna = int(c.fetchone()[0] or 0)
        c.execute("SELECT COUNT(*) FROM ir_sessions")
        n_ir = int(c.fetchone()[0] or 0)
        return {"sauna": n_sauna, "ir": n_ir}
    except Exception:
        return {"sauna": 0, "ir": 0}
    finally:
        conn.close()


def count_learns(db_path: str) -> Dict[str, int]:
    """Sessions where learn produced a measured W (audit column set)."""
    conn = sqlite3.connect(db_path)
    try:
        ensure_schema(conn)
        c = conn.cursor()
        c.execute(
            """
            SELECT COUNT(*) FROM sauna_sessions
            WHERE audit_measured_w_u IS NOT NULL
               OR audit_measured_w_v IS NOT NULL
               OR audit_measured_w_w IS NOT NULL
            """
        )
        n_sauna = int(c.fetchone()[0] or 0)
        c.execute(
            "SELECT COUNT(*) FROM ir_sessions WHERE audit_measured_w_ir IS NOT NULL"
        )
        n_ir = int(c.fetchone()[0] or 0)
        return {"sauna": n_sauna, "ir": n_ir}
    except Exception:
        return {"sauna": 0, "ir": 0}
    finally:
        conn.close()


def row_to_dict(
    row: ElementPowerRow,
    session_counts: Optional[Dict[str, int]] = None,
    learn_counts: Optional[Dict[str, int]] = None,
) -> dict:
    out: Dict[str, Any] = {
        "w_u": row.w_u,
        "w_v": row.w_v,
        "w_w": row.w_w,
        "w_ir": row.w_ir,
        "updated_at": row.updated_at,
        "learn_count_sauna": (
            int(learn_counts["sauna"])
            if learn_counts is not None and "sauna" in learn_counts
            else row.learn_count_sauna
        ),
        "learn_count_ir": (
            int(learn_counts["ir"])
            if learn_counts is not None and "ir" in learn_counts
            else row.learn_count_ir
        ),
        "last_learn_sauna_status": row.last_learn_sauna_status,
        "last_learn_sauna_detail": row.last_learn_sauna_detail,
        "last_learn_sauna_at": row.last_learn_sauna_at,
        "last_learn_ir_status": row.last_learn_ir_status,
        "last_learn_ir_measured_w": row.last_learn_ir_measured_w,
        "last_learn_ir_at": row.last_learn_ir_at,
    }
    if session_counts is not None:
        out["session_count_sauna"] = int(session_counts.get("sauna", 0))
        out["session_count_ir"] = int(session_counts.get("ir", 0))
    return out
