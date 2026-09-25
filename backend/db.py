"""
db.py - SQLite database models and helper functions for AutoFormFiller.
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "autoformfiller.db")


def get_conn():
    """Return a new SQLite connection with row_factory set to Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL UNIQUE,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profile_fields (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id  INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                field_key   TEXT    NOT NULL,
                field_value TEXT    NOT NULL,
                UNIQUE(profile_id, field_key)
            )
            """
        )
        conn.commit()


# ── Profile helpers ───────────────────────────────────────────────────────────

def list_profiles():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at, updated_at FROM profiles ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_profile(profile_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, created_at, updated_at FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        if not row:
            return None
        profile = dict(row)
        fields = conn.execute(
            "SELECT field_key, field_value FROM profile_fields WHERE profile_id = ?",
            (profile_id,),
        ).fetchall()
        profile["fields"] = {f["field_key"]: f["field_value"] for f in fields}
    return profile


def create_or_update_profile(name: str, fields: dict):
    """
    Upsert a profile by name and replace all its fields.
    Returns the profile id.
    """
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO profiles (name) VALUES (?)
            ON CONFLICT(name) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
            """,
            (name,),
        )
        row = conn.execute("SELECT id FROM profiles WHERE name = ?", (name,)).fetchone()
        profile_id = row["id"]

        # Replace all fields
        conn.execute("DELETE FROM profile_fields WHERE profile_id = ?", (profile_id,))
        for key, value in fields.items():
            conn.execute(
                "INSERT INTO profile_fields (profile_id, field_key, field_value) VALUES (?, ?, ?)",
                (profile_id, key, str(value)),
            )
        conn.commit()
    return profile_id


def delete_profile(profile_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        conn.commit()
