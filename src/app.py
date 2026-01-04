from flask import Flask, render_template, request, redirect, session
import os
import csv
import threading

import auth
import database
from gmail_dataset_builder import sync_gmail_to_csv

app = Flask(__name__)
app.secret_key = "coursework-secret-key"

DB_PATH = "data/users.db"


def get_user_dir(user_id):
    path = os.path.join("user_data", f"user_{user_id}")
    os.makedirs(path, exist_ok=True)
    return path


@app.route("/")
def index():
    if "user" in session:
        return redirect("/dashboard")
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = auth.login_user(email, password, DB_PATH)
        if not user:
            return render_template("login.html", error="Invalid credentials")

        session["user"] = user

        user_dir = get_user_dir(user["id"])
        threading.Thread(
            target=sync_gmail_to_csv,
            args=(user["email"], user["app_password"], user_dir),
            daemon=True
        ).start()

        return redirect("/dashboard")

    return render_template("login.html", error=None)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        ok, msg = auth.register_user(
            request.form["email"],
            request.form["password"],
            request.form["imap"],
            DB_PATH
        )
        if not ok:
            return render_template("register.html", error=msg)

        return redirect("/login")

    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    user = session["user"]
    user_dir = get_user_dir(user["id"])
    csv_path = os.path.join(user_dir, "imap_email.csv")

    emails = []
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8") as f:
            emails = list(csv.DictReader(f))

    # pagination-safe
    page = int(request.args.get("page", 1))
    per_page = 15
    total = len(emails)
    total_pages = max(1, (total + per_page - 1) // per_page)

    start = (page - 1) * per_page
    end = start + per_page

    return render_template(
        "dashboard.html",
        emails=emails[start:end],
        email_count=total,
        page=page,
        total_pages=total_pages,
        user_email=user["email"]
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    database.init_db(DB_PATH)
    app.run()
