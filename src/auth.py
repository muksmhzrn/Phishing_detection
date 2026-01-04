import os
import json
import uuid
import sqlite3

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
USER_DATA_DIR = os.path.join(BASE_DIR, "data", "user_data")
DB_PATH = os.path.join(BASE_DIR, "data", "users.db")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(USER_DATA_DIR, exist_ok=True)

# Initialize DB
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    password TEXT
)
""")
conn.commit()
conn.close()


def register_user(email, password, app_password):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            return None  # email exists

        user_id = str(uuid.uuid4())

        cursor.execute(
            "INSERT INTO users (id, email, password) VALUES (?, ?, ?)",
            (user_id, email, password)
        )
        conn.commit()
        conn.close()

        user_dir = os.path.join(USER_DATA_DIR, user_id)
        os.makedirs(user_dir, exist_ok=True)

        meta_path = os.path.join(user_dir, "meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"email": email, "app_password": app_password}, f, indent=2)

        return user_id

    except Exception as e:
        print(f"[REGISTER ERROR] {e}")
        return None


def login_user(email, password):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()

        if row:
            user_id, stored_password = row
            if password == stored_password:
                return user_id
        return None
    except Exception as e:
        print(f"[LOGIN ERROR] {e}")
        return None


def get_user_gmail_credentials(user_id):
    try:
        meta_path = os.path.join(USER_DATA_DIR, user_id, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"[GMAIL CREDENTIALS ERROR] {e}")
        return None
