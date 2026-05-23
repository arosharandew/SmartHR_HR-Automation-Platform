"""
Database.py - Database schema and connection.
All CRUD operations moved to Helper.py.
"""

import sqlite3
from pathlib import Path

DATABASE_FILE = Path(__file__).parent / "hr_platform.db"

def get_db_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def create_tables() -> None:
    """Create all tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nic TEXT,
            phone TEXT,
            designation TEXT,
            department TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)

    # 2. Scheduling table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduling (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            schedule_type TEXT NOT NULL,
            with_whom TEXT,
            user_prompt TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    # 3. Leave requests table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            leave_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            user_prompt TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    # 4. Compliance queries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compliance_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    # 5. Audit log table (append-only)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            raw_input TEXT NOT NULL,
            intent TEXT,
            confidence REAL,
            routed_agent TEXT,
            response TEXT,
            latency_ms INTEGER,
            error TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    # 6. Short-term memory table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS short_term_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            turn_index INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 7. Long-term memory table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS long_term_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            session_id TEXT,
            fact_key TEXT NOT NULL,
            fact_value TEXT NOT NULL,
            significance_score REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    # 8. Session state table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_state (
            session_id TEXT PRIMARY KEY,
            last_agent TEXT,
            pending_action TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 9. Leave balances table (default: 21 vacation days, 10 sick days, 5 casual days)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leave_balances (
            user_id TEXT PRIMARY KEY,
            vacation_days REAL DEFAULT 21.0,
            sick_days REAL DEFAULT 10.0,
            casual_days REAL DEFAULT 5.0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    # 10. Public holidays table (optional, for compliance agent)
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS public_holidays(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            name TEXT NOT NULL,
            year INTEGER NOT NULL
                   )
    """)

    conn.commit()
    conn.close()
    print("✅ All 10 tables created successfully.")

def initialize_holidays() -> None:
    """Insert default public holidays for Sri Lanka (example)."""
    holidays = [
        ("2026-01-14", "Tamil Thai Pongal Day", 2026),
        ("2026-02-04", "Independence Day", 2026),
        ("2026-04-13", "Sinhala and Tamil New Year", 2026),
        ("2026-04-14", "Sinhala and Tamil New Year", 2026),
        ("2026-05-01", "May Day", 2026),
        ("2026-05-22", "Vesak Full Moon Poya Day", 2026),
        ("2026-05-23", "Vesak Full Moon Poya Day", 2026),
    ]
    conn = get_db_connection()
    cursor = conn.cursor()
    for date, name, year in holidays:
        cursor.execute("""
            INSERT OR IGNORE INTO public_holidays (date, name, year)
            VALUES (?, ?, ?)
        """, (date, name, year))
    conn.commit()
    conn.close()
    print("✅ Public holidays initialized.")

if __name__ == "__main__":
    create_tables()
    initialize_holidays()