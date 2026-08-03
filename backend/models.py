"""
models.py
Database layer for Project Report Generator.
Uses plain sqlite3 (no ORM) for transparency and simplicity - suitable
for a B.Tech mini project. All DB access goes through helper functions
in this module so app.py stays clean.
"""

import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "database.db")


def get_db():
    """Return a sqlite3 connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    department TEXT DEFAULT '',
    college TEXT DEFAULT '',
    photo TEXT DEFAULT 'default_avatar.png',
    is_admin INTEGER DEFAULT 0,
    dark_mode INTEGER DEFAULT 0,
    notifications INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    icon TEXT DEFAULT 'bi-file-earmark-text',
    accent TEXT DEFAULT 'primary',
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    template_slug TEXT NOT NULL,
    data_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    project_title TEXT NOT NULL,
    template_slug TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    report_id INTEGER NOT NULL,
    file_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    downloaded_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
);

-- NEW: Team / Collaboration (shared access, take-turns editing)
CREATE TABLE IF NOT EXISTS collaborators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    invited_at TEXT NOT NULL,
    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- NEW: Notifications (lightweight activity feed)
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    type TEXT DEFAULT 'info',
    is_read INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- NEW: AI Assistant chat log (persisted so Search can find past messages)
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    report_id INTEGER,
    role TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE SET NULL
);
"""

DEFAULT_TEMPLATES = [
    ("Mini Project Template", "mini-project",
     "Perfect for 2nd/3rd year semester mini projects with concise chapters.",
     "bi-journal-code", "primary"),
    ("Major Project Template", "major-project",
     "Comprehensive structure for final year major/capstone projects.",
     "bi-mortarboard", "purple"),
    ("Internship Template", "internship",
     "Document your internship experience, tasks and learnings.",
     "bi-briefcase", "info"),
    ("Research Paper", "research-paper",
     "Formal academic structure with abstract, methodology and references.",
     "bi-file-earmark-richtext", "success"),
    ("Seminar Report", "seminar-report",
     "Compact report format ideal for seminar submissions.",
     "bi-easel", "warning"),
    ("Industrial Training", "industrial-training",
     "Report structure tailored to industrial training / in-plant training.",
     "bi-building-gear", "danger"),
]


def _ensure_column(conn, table, column, coltype):
    """
    NEW: safe migration helper.
    If you already have an old database.db from before these features existed,
    'CREATE TABLE IF NOT EXISTS' won't add new columns to it. This checks the
    existing columns and ALTERs the table only if the column is missing, so
    your existing users/reports/downloads data is kept, not wiped.
    """
    existing_cols = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
    if column not in existing_cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")


def init_db(app=None):
    """Create tables if they do not exist, migrate old ones, and seed default data."""
    os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()

    # NEW: migrate an older reports table that predates Trash/Archive
    _ensure_column(conn, "reports", "is_deleted", "INTEGER DEFAULT 0")
    _ensure_column(conn, "reports", "deleted_at", "TEXT")
    conn.commit()

    # Seed templates
    existing = conn.execute("SELECT COUNT(*) c FROM templates").fetchone()["c"]
    if existing == 0:
        for name, slug, desc, icon, accent in DEFAULT_TEMPLATES:
            conn.execute(
                "INSERT INTO templates (name, slug, description, icon, accent) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, slug, desc, icon, accent),
            )
        conn.commit()

    # Seed a demo admin + demo user so the app is usable out of the box
    admin = conn.execute("SELECT id FROM users WHERE email = ?",
                          ("admin@reportgen.com",)).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO users (name, email, password_hash, department, college, "
            "is_admin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Administrator", "admin@reportgen.com",
             generate_password_hash("admin123"),
             "Computer Science", "Demo Engineering College", 1,
             datetime.now().isoformat()),
        )
    demo = conn.execute("SELECT id FROM users WHERE email = ?",
                         ("demo@reportgen.com",)).fetchone()
    if not demo:
        conn.execute(
            "INSERT INTO users (name, email, password_hash, department, college, "
            "is_admin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Demo Student", "demo@reportgen.com",
             generate_password_hash("demo1234"),
             "Computer Science", "Demo Engineering College", 0,
             datetime.now().isoformat()),
        )
    conn.commit()
    conn.close()