import os, json, uuid, sqlite3
from functools import wraps
from flask import session, redirect, url_for

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
USER_DATA_DIR = os.path.join(DATA_DIR, "user_data")
DB_PATH = os.path.join(DATA_DIR, "users.db")

os.makedirs(USER_DATA_DIR, exist_ok=True)

def get_db():
    return sqlite3.connect(DB_PATH)

# DB init
with get_db() as conn:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

def register_user(email, password, app_password):
    try:
        user_id = str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users VALUES (?, ?, ?)",
                (user_id, email, password)
            )

        user_dir = os.path.join(USER_DATA_DIR, user_id)
        os.makedirs(user_dir, exist_ok=True)

        with open(os.path.join(user_dir, "meta.json"), "w") as f:
            json.dump({"email": email, "app_password": app_password}, f, indent=2)

        return user_id
    except sqlite3.IntegrityError:
        return None

def login_user(email, password):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE email=? AND password=?",
            (email, password)
        ).fetchone()
        return row[0] if row else None

def get_user_gmail_credentials(user_id):
    path = os.path.join(USER_DATA_DIR, user_id, "meta.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return wrapper
