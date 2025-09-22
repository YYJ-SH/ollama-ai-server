# 데이터베이스 관련 로직
import sqlite3
from . import config

def init_db():
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            owner TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            request_count INTEGER NOT NULL DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

async def validate_and_log_key(api_key: str):
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM api_keys WHERE key = ? AND is_active = 1", (api_key,))
    key_data = cursor.fetchone()
    if not key_data:
        conn.close()
        return None
    cursor.execute("UPDATE api_keys SET request_count = request_count + 1 WHERE id = ?", (key_data['id'],))
    conn.commit()
    conn.close()
    return dict(key_data)