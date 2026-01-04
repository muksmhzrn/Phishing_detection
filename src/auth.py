import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash


def register_user(email, password, app_password, db_path):
    if not email or not password or not app_password:
        return False  # prevents 400

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO users (email, password, app_password) VALUES (?, ?, ?)",
            (email, generate_password_hash(password), app_password)
        )
        conn.commit()
        return True

    except sqlite3.IntegrityError:
        return False  # duplicate email

    finally:
        conn.close()


def login_user(email, password, db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cur.fetchone()
    conn.close()

    if user and check_password_hash(user["password"], password):
        return dict(user)

    return None
