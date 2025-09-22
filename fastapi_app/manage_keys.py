import sqlite3
import secrets
import string
import argparse
from datetime import datetime
import os

# Docker 컨테이너 내부의 DB 파일 경로를 사용합니다.
# 이 경로는 docker-compose.yml의 볼륨 설정과 일치해야 합니다.
DATABASE_FILE = "/app/database/api_server.db"

def init_db_path():
    """Ensure the database directory exists."""
    db_dir = os.path.dirname(DATABASE_FILE)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

def generate_api_key(length=16):
    """Generates a cryptographically secure API key."""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def add_key(owner):
    """Adds a new API key to the database."""
    init_db_path()
    new_key = generate_api_key()
    conn = sqlite3.connect(DATABASE_FILE)
    # DB가 없으면 생성하는 로직도 필요합니다.
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
    try:
        cursor.execute(
            "INSERT INTO api_keys (key, owner, created_at) VALUES (?, ?, ?)",
            (new_key, owner, datetime.now().isoformat())
        )
        conn.commit()
        print(f"✅ Successfully added new key for '{owner}': {new_key}")
    except sqlite3.IntegrityError:
        print("Error: Could not add key. This should not happen.")
    finally:
        conn.close()

def revoke_key(key):
    """Revokes an existing API key."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE api_keys SET is_active = 0 WHERE key = ?", (key,))
    conn.commit()
    if cursor.rowcount > 0:
        print(f"🔑 Key '{key}' has been revoked.")
    else:
        print(f"⚠️ Key '{key}' not found.")
    conn.close()

def list_keys():
    """Lists all API keys in the database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM api_keys")
        keys = cursor.fetchall()
        conn.close()
        
        print("--- API Keys ---")
        for key in keys:
            status = "Active" if key['is_active'] else "Inactive"
            print(f"Owner: {key['owner']:<15} | Key: {key['key']:<20} | Status: {status:<10} | Requests: {key['request_count']}")
        print("----------------")
    except sqlite3.OperationalError:
        print("⚠️ No keys found or database not initialized. Please add a key first.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage API keys for the AI server.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_add = subparsers.add_parser("add", help="Add a new API key.")
    parser_add.add_argument("owner", type=str, help="The owner of the key (e.g., 'project_x').")

    parser_revoke = subparsers.add_parser("revoke", help="Revoke an existing API key.")
    parser_revoke.add_argument("key", type=str, help="The API key to revoke.")

    parser_list = subparsers.add_parser("list", help="List all API keys.")

    args = parser.parse_args()

    if args.command == "add":
        add_key(args.owner)
    elif args.command == "revoke":
        revoke_key(args.key)
    elif args.command == "list":
        list_keys()