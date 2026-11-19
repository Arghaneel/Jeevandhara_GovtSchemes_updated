"""SQLite storage for Jeevandhara.

Each request opens its own short-lived connection through ``get_connection()``,
which is safe with FastAPI's worker threads (a single shared cursor is not).
The schema is created, and older databases are migrated, on import.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# The database always lives next to this file unless JEEVANDHARA_DB says
# otherwise, so the app works no matter which folder uvicorn is started from.
DB_PATH = Path(os.getenv("JEEVANDHARA_DB", str(BASE_DIR / "jeevandhara.db")))


def _connect():
    connection = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def get_connection():
    """Yield a connection that commits on success and rolls back on error."""
    connection = _connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


OPTIONAL_PROFILE_COLUMNS = (
    ("land_ownership", "TEXT"),      # owner | tenant | landless
    ("income_tax_payer", "INTEGER"),  # 0 / 1
    ("govt_employee", "INTEGER"),
    ("social_security", "INTEGER"),   # covered by NPS / EPFO / ESIC
    ("has_bank_account", "INTEGER"),
    ("social_category", "TEXT"),     # general | obc | sc | st
    ("gender", "TEXT"),              # male | female | other
)


def _column_names(connection, table):
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}


def init_db():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS farmers(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                name TEXT,
                age INTEGER,
                income REAL,
                land_size REAL,
                state TEXT,
                district TEXT
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question TEXT,
                answer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scheme_name TEXT
            )
            """
        )

        # Saved schemes: application status and document checklist per farmer.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_schemes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                scheme_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'interested',
                documents_done TEXT NOT NULL DEFAULT '[]',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, scheme_name)
            )
            """
        )

        # Migrations for databases created by earlier versions of the app.
        # The chatbot remembers which scheme a conversation is about:
        if "scheme_name" not in _column_names(connection, "chat_history"):
            connection.execute("ALTER TABLE chat_history ADD COLUMN scheme_name TEXT")

        # Optional profile questions used for exclusion rules (NULL = not answered):
        farmer_columns = _column_names(connection, "farmers")
        for column, column_type in OPTIONAL_PROFILE_COLUMNS:
            if column not in farmer_columns:
                connection.execute(f"ALTER TABLE farmers ADD COLUMN {column} {column_type}")

        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_history_user ON chat_history(user_id)"
        )


init_db()

# Kept for older helper scripts (e.g. test_db.py) that import these directly.
# The API itself uses get_connection().
conn = _connect()
cursor = conn.cursor()
