# fastapi_app/app/database.py

import sqlite3
from . import config
from datetime import datetime

def init_db():
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    
    # api_keys 테이블 생성 (예약어 key → api_key 로 변경)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key TEXT NOT NULL UNIQUE,
            owner TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            request_count INTEGER NOT NULL DEFAULT 0
        )
    ''')
    
    # logs 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key_owner TEXT NOT NULL,
            model_used TEXT NOT NULL,
            prompt TEXT,
            response TEXT,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

async def validate_and_log_key(api_key: str):
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM api_keys WHERE api_key = ? AND is_active = 1", (api_key,))
    key_data = cursor.fetchone()
    
    if not key_data:
        conn.close()
        return None
    
    cursor.execute("UPDATE api_keys SET request_count = request_count + 1 WHERE id = ?", (key_data['id'],))
    conn.commit()
    conn.close()
    return dict(key_data)

async def add_api_log(owner: str, model: str, prompt: str, response: str):
    conn = sqlite3.connect(config.DATABASE_FILE)
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    try:
        cursor.execute(
            "INSERT INTO logs (api_key_owner, model_used, prompt, response, timestamp) VALUES (?, ?, ?, ?, ?)",
            (owner, model, prompt, response, timestamp)
        )
        conn.commit()
    except Exception as e:
        print(f"DB 로그 기록 실패: {e}")
    finally:
        conn.close()
