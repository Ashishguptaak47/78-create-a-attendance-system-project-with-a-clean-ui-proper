import sqlite3
from datetime import datetime, date

def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        department TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'Member',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        check_in TEXT,
        check_out TEXT,
        status TEXT NOT NULL CHECK(status IN ('Present', 'Late', 'Absent', 'Excused')),
        note TEXT,
        UNIQUE(member_id, date),
        FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE
    );
    """)
    
    # Seed sample members if table is empty
    cursor.execute("SELECT COUNT(*) as count FROM members;")
    if cursor.fetchone()["count"] == 0:
        now = datetime.now().isoformat()
        samples = [
            ("EMP001", "Alice Smith", "alice@example.com", "Engineering", "Software Engineer", 1, now),
            ("EMP002", "Bob Jones", "bob@example.com", "Marketing", "Brand Manager", 1, now),
            ("EMP003", "Clara Oswald", "clara@example.com", "Design", "UI/UX Designer", 1, now),
            ("EMP004", "David Miller", "david@example.com", "Engineering", "DevOps Engineer", 1, now),
            ("EMP005", "Elena Rostova", "elena@example.com", "Operations", "Project Manager", 1, now),
        ]
        cursor.executemany(
            "INSERT INTO members (code, name, email, department, role, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            samples
        )
        conn.commit()
    conn.close()
