import sqlite3
import os
from datetime import datetime

DB_PATH = "bot.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            prompt TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    conn.commit()
    conn.close()

def get_or_create_user(telegram_id, username=None, first_name=None):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute(
            "INSERT INTO users (telegram_id, username, first_name) VALUES (?, ?, ?)",
            (telegram_id, username, first_name)
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user = cursor.fetchone()
    
    conn.close()
    return dict(user)

def set_admin(telegram_id, is_admin=1):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_admin = ? WHERE telegram_id = ?", (is_admin, telegram_id))
    conn.commit()
    conn.close()

def is_admin(telegram_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    conn.close()
    return row and row[0] == 1

def log_request(user_id, prompt, status, error_message=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logs (user_id, prompt, status, error_message) VALUES (?, ?, ?, ?)",
        (user_id, prompt, status, error_message)
    )
    conn.commit()
    conn.close()

def get_logs(limit=50, offset=0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.*, u.username, u.first_name 
        FROM logs l
        LEFT JOIN users u ON l.user_id = u.id
        ORDER BY l.created_at DESC
        LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_user_stats():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            u.telegram_id,
            u.username,
            u.first_name,
            COUNT(l.id) as total_requests,
            SUM(CASE WHEN l.status = 'success' THEN 1 ELSE 0 END) as successful
        FROM users u
        LEFT JOIN logs l ON u.id = l.user_id
        WHERE u.is_admin = 1
        GROUP BY u.id
        ORDER BY total_requests DESC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_admins():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM users WHERE is_admin = 1")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

init_db()