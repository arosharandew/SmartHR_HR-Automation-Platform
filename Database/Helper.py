"""
Helper.py - CRUD operations for the HR Automation Platform.
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
from .Database import get_db_connection

# ========== USERS ==========
def create_user(user_id: str, name: str, email: str, password_hash: str,
                nic: str = None, phone: str = None, designation: str = None,
                department: str = None) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (user_id, name, email, password_hash, nic, phone, designation, department)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, name, email, password_hash, nic, phone, designation, department))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_any(identifier: str) -> Optional[Dict[str, Any]]:
    """Find user by email, phone, or user_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM users WHERE email = ? OR phone = ? OR user_id = ?
    """, (identifier, identifier, identifier))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_last_login(user_id: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_last_user_id() -> Optional[str]:
    """Return the most recent user_id, e.g., 'CD042'."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users ORDER BY user_id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row["user_id"] if row else None

# ========== SCHEDULING ==========
def insert_schedule(user_id: str, date: str, time: str, day_of_week: str,
                    schedule_type: str, user_prompt: str, with_whom: str = None) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO scheduling (user_id, date, time, day_of_week, schedule_type, with_whom, user_prompt)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, date, time, day_of_week, schedule_type, with_whom, user_prompt))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def get_user_schedules(user_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scheduling WHERE user_id = ? ORDER BY date, time", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_schedule_by_id(schedule_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scheduling WHERE id = ?", (schedule_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_meetings_by_date(user_id: str, date: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM scheduling 
        WHERE user_id = ? AND date = ? 
        ORDER BY time
    """, (user_id, date))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_meetings_by_type(user_id: str, schedule_type: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM scheduling 
        WHERE user_id = ? AND schedule_type = ? 
        ORDER BY date, time
    """, (user_id, schedule_type))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_upcoming_meetings(user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM scheduling 
        WHERE user_id = ? AND date >= ? 
        ORDER BY date, time 
        LIMIT ?
    """, (user_id, today, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ========== LEAVE REQUESTS ==========
def insert_leave_request(user_id: str, start_date: str, end_date: str,
                         leave_type: str, user_prompt: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO leave_requests (user_id, start_date, end_date, leave_type, user_prompt)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, start_date, end_date, leave_type, user_prompt))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def update_leave_status(request_id: int, status: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE leave_requests SET status = ? WHERE id = ?", (status, request_id))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated

def get_user_leave_requests(user_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leave_requests WHERE user_id = ? ORDER BY start_date DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ========== COMPLIANCE QUERIES ==========
def insert_compliance_query(user_id: str, question: str, answer: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO compliance_queries (user_id, question, answer)
        VALUES (?, ?, ?)
    """, (user_id, question, answer))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

# ========== AUDIT LOG ==========
def log_audit(user_id: str, session_id: str, raw_input: str,
              intent: str, confidence: float, routed_agent: str,
              response: str, latency_ms: int, error: str = None) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_log (user_id, session_id, raw_input, intent, confidence,
                               routed_agent, response, latency_ms, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, session_id, raw_input, intent, confidence,
          routed_agent, response, latency_ms, error))
    conn.commit()
    log_id = cursor.lastrowid
    conn.close()
    return log_id

def get_audit_log(session_id: str = None, user_id: str = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if session_id:
        cursor.execute("SELECT * FROM audit_log WHERE session_id = ? ORDER BY timestamp", (session_id,))
    elif user_id:
        cursor.execute("SELECT * FROM audit_log WHERE user_id = ? ORDER BY timestamp", (user_id,))
    else:
        cursor.execute("SELECT * FROM audit_log ORDER BY timestamp")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ========== SHORT‑TERM MEMORY ==========
def add_stm_turn(session_id: str, turn_index: int, role: str, content: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO short_term_memory (session_id, turn_index, role, content)
        VALUES (?, ?, ?, ?)
    """, (session_id, turn_index, role, content))
    conn.commit()
    conn.close()

def get_stm_context(session_id: str, last_n_turns: int = 5) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content FROM short_term_memory
        WHERE session_id = ?
        ORDER BY turn_index DESC LIMIT ?
    """, (session_id, last_n_turns))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in reversed(rows)]

def clear_stm(session_id: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM short_term_memory WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

# ========== LONG‑TERM MEMORY ==========
def add_ltm_fact(user_id: str, fact_key: str, fact_value: str,
                 significance_score: float = 0.5, session_id: str = None,
                 expires_at: str = None) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO long_term_memory (user_id, session_id, fact_key, fact_value, significance_score, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, session_id, fact_key, fact_value, significance_score, expires_at))
    conn.commit()
    fact_id = cursor.lastrowid
    conn.close()
    return fact_id

def get_ltm_facts(user_id: str, min_significance: float = 0.0) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fact_key, fact_value, significance_score FROM long_term_memory
        WHERE user_id = ? AND significance_score >= ?
        AND (expires_at IS NULL OR expires_at > datetime('now'))
        ORDER BY significance_score DESC
    """, (user_id, min_significance))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ========== SESSION STATE ==========
def set_session_state(session_id: str, last_agent: str, pending_action: str = None) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO session_state (session_id, last_agent, pending_action, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    """, (session_id, last_agent, pending_action))
    conn.commit()
    conn.close()

def get_session_state(session_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM session_state WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# ========== LEAVE BALANCES ==========
def get_or_create_leave_balance(user_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leave_balances WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
            INSERT INTO leave_balances (user_id, vacation_days, sick_days)
            VALUES (?, 21.0, 10.0)
        """, (user_id,))
        conn.commit()
        cursor.execute("SELECT * FROM leave_balances WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    conn.close()
    return dict(row)

def update_leave_balance(user_id: str, vacation_days: float = None, sick_days: float = None) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    updates, params = [], []
    if vacation_days is not None:
        updates.append("vacation_days = ?")
        params.append(vacation_days)
    if sick_days is not None:
        updates.append("sick_days = ?")
        params.append(sick_days)
    if not updates:
        return False
    params.append(user_id)
    cursor.execute(f"UPDATE leave_balances SET {', '.join(updates)}, last_updated = CURRENT_TIMESTAMP WHERE user_id = ?", params)
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated

# ========== SCHEDULING - UPDATE & DELETE ==========
def update_schedule(schedule_id: int, **kwargs) -> bool:
    """
    Update specific fields of a schedule entry.
    kwargs can contain: date, time, day_of_week, schedule_type, with_whom
    Returns True if successful.
    """
    allowed = {"date", "time", "day_of_week", "schedule_type", "with_whom"}
    updates = []
    params = []
    for key, value in kwargs.items():
        if key in allowed and value is not None:
            updates.append(f"{key} = ?")
            params.append(value)
    if not updates:
        return False
    params.append(schedule_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE scheduling SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated

def delete_schedule(schedule_id: int) -> bool:
    """Delete a schedule entry by ID. Returns True if deleted."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scheduling WHERE id = ?", (schedule_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

# Add this to Helper.py (inside the SCHEDULING section)

def find_meetings_by_attendee(user_id: str, attendee_name: str, date: str = None) -> List[Dict[str, Any]]:
    """
    Find meetings by attendee name (case‑insensitive, partial match).
    If date is provided (YYYY-MM-DD), also filter by that date.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT * FROM scheduling 
        WHERE user_id = ? AND LOWER(with_whom) LIKE ?
    """
    params = [user_id, f"%{attendee_name.lower()}%"]
    if date:
        query += " AND date = ?"
        params.append(date)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
def get_stm_turn_count(session_id: str) -> int:
    """Get the number of turns in STM for a session."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM short_term_memory WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    return row["count"] if row else 0

def clear_old_stm(session_id: str, keep_last: int = 50) -> None:
    """Delete old STM entries beyond keep_last count."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM short_term_memory 
        WHERE session_id = ? AND id NOT IN (
            SELECT id FROM short_term_memory 
            WHERE session_id = ? 
            ORDER BY id DESC LIMIT ?
        )
    """, (session_id, session_id, keep_last))
    conn.commit()
    conn.close()

def get_meetings_between(user_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Get meetings between two dates (YYYY-MM-DD)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM scheduling 
        WHERE user_id = ? AND date BETWEEN ? AND ?
        ORDER BY date, time
    """, (user_id, start_date, end_date))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def check_availability(user_id: str, date: str, time: str) -> bool:
    """Check if user is free at a specific date/time."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as count FROM scheduling 
        WHERE user_id = ? AND date = ? AND time = ?
    """, (user_id, date, time))
    row = cursor.fetchone()
    conn.close()
    return row["count"] == 0

def get_upcoming_meetings_count(user_id: str) -> int:
    """Get count of upcoming meetings."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as count FROM scheduling 
        WHERE user_id = ? AND date >= ?
    """, (user_id, today))
    row = cursor.fetchone()
    conn.close()
    return row["count"] if row else 0

def delete_meetings_by_date(user_id: str, date: str) -> int:
    """Delete all meetings on a specific date. Returns number deleted."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scheduling WHERE user_id = ? AND date = ?", (user_id, date))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted

def delete_meetings_by_attendee_and_date_range(user_id: str, attendee: str, start_date: str, end_date: str) -> int:
    """Delete meetings with attendee within date range."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM scheduling 
        WHERE user_id = ? AND LOWER(with_whom) LIKE ? 
        AND date BETWEEN ? AND ?
    """, (user_id, f"%{attendee.lower()}%", start_date, end_date))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted

def get_public_holidays(year: int) -> List[Dict[str, Any]]:
    """Get public holidays for a year (create table if needed)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Create table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS public_holidays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            name TEXT NOT NULL,
            year INTEGER NOT NULL
        )
    """)
    conn.commit()
    cursor.execute("SELECT * FROM public_holidays WHERE year = ? ORDER BY date", (year,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]