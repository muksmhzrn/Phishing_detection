import os
import csv
import math
from threading import Thread
from flask import Flask, render_template, request, redirect, session, url_for

from auth import login_user, register_user
from database import init_db
from gmail_dataset_builder import sync_gmail_to_csv

# ------------------ CONFIG ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "user_data")
DB_PATH = os.path.join(BASE_DIR, "data", "users.db")

EMAILS_PER_PAGE = 15
# --------------------------------------------

app = Flask(__name__)
app.secret_key = "change_this_for_production"

# Ensure base folders exist
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize database
init_db(DB_PATH)

# ------------------ HELPERS ------------------

def get_user_csv(user_id):
    user_dir = os.path.join(DATA_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, "imap_emails.csv")


def load_emails(csv_path):
    if not os.path.exists(csv_path):
        return []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


# ------------------ ROUTES ------------------

@app.route("/")
def index():
    if "user_id" in session:
        return redirect("/dashboard")
    return redirect("/login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        app_password = request.form["app_password"]

        success = register_user(email, password, app_password, DB_PATH)
        if success:
            return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = login_user(email, password, DB_PATH)
        if user:
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            session["app_password"] = user["app_password"]

            # ---------- BACKGROUND GMAIL SYNC ----------
            csv_path = get_user_csv(user["id"])

            Thread(
                target=sync_gmail_to_csv,
                args=(user["email"], user["app_password"], csv_path),
                daemon=True
            ).start()
            # ------------------------------------------

            return redirect("/dashboard")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    csv_path = get_user_csv(user_id)

    emails = load_emails(csv_path)
    total_emails = len(emails)

    page = request.args.get("page", 1, type=int)
    total_pages = max(1, math.ceil(total_emails / EMAILS_PER_PAGE))

    start = (page - 1) * EMAILS_PER_PAGE
    end = start + EMAILS_PER_PAGE
    emails_page = emails[start:end]

    phishing_count = sum(1 for e in emails if e.get("label") == "Phishing")
    legit_count = total_emails - phishing_count

    return render_template(
        "dashboard.html",
        emails=emails_page,
        email_count=total_emails,
        phishing_count=phishing_count,
        legit_count=legit_count,
        page=page,
        total_pages=total_pages,
        user_email=session.get("email")
    )


@app.route("/soc")
def soc_alerts():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    csv_path = get_user_csv(user_id)

    emails = load_emails(csv_path)

    alerts = [
        e for e in emails
        if float(e.get("phishing_probability", 0)) >= 0.8
    ]

    return render_template(
        "soc.html",
        alerts=alerts,
        user_email=session.get("email")
    )


# ------------------ RUN ------------------

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
