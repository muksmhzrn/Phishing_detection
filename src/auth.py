import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

import database


def register_user(email: str, password: str, app_password: str, db_path: str):
    """
    Returns: (ok: bool, message: str)
    - Enforces unique email
    - Stores password hash + app_password (IMAP field from register form)
    """
    if not email or not password or not app_password:
        return False, "Email, password, and Gmail App Password are required."

    pw_hash = generate_password_hash(password)

    try:
        conn = database.get_conn(db_path)
        conn.execute(
            "INSERT INTO users (email, password_hash, app_password) VALUES (?, ?, ?)",
            (email, pw_hash, app_password),
        )
        conn.commit()
        conn.close()
        return True, "OK"
    except sqlite3.IntegrityError:
        return False, "Email already registered. Please login."
    except Exception:
        return False, "Registration failed due to a server error."


def login_user(email: str, password: str, db_path: str):
    """
    Returns user dict {id,email,app_password} or None
    """
    if not email or not password:
        return None

    conn = database.get_conn(db_path)
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if not user:
        return None

    if not check_password_hash(user["password_hash"], password):
        return None

    return {"id": user["id"], "email": user["email"], "app_password": user["app_password"]}