from flask import Flask, render_template, request, redirect, session
from auth import register_user, login_user, get_user_gmail_credentials
from gmail_dataset_builder import sync_gmail_to_csv
import subprocess, threading, os, time
from flask import Flask, render_template, request, redirect, session, url_for
import os
from database import init_db
from auth import login_required

app = Flask(__name__)
app.secret_key = "supersecretkey"  # for session


MODEL_FILES = {
    "baseline": "imap_emails_with_predictions_logistic.csv",
    "xgboost": "imap_emails_with_predictions_xgb.csv"
}
# Initialize database

# Keep track of running sync threads per user
user_sync_threads = {}

# =======================
# REGISTRATION
# =======================
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    success = None
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        app_password = request.form["app_password"]

        user_id = register_user(email, password, app_password)
        if user_id:
            success = "Registration successful! You can login now."
        else:
            error = "Email already registered or error occurred."

    return render_template("register.html", error=error, success=success)


# =======================
# LOGIN
# =======================
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user_id = login_user(email, password)
        if user_id:
            session["user_id"] = user_id

            # Start Gmail sync in background
            start_background_sync(user_id, email)

            return redirect("/dashboard")
        else:
            error = "Invalid email or password"

    return render_template("login.html", error=error)

# =======================
# DASHBOARD
# =======================
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    model = request.args.get("model", "baseline")

    user_data_dir = os.path.join("data", "user_data", user_id)

    csv_file = MODEL_FILES.get(model, MODEL_FILES["baseline"])
    csv_path = os.path.join(user_data_dir, csv_file)

    baseline_data = []

    if os.path.exists(csv_path):
        import pandas as pd
        df = pd.read_csv(csv_path)

        # ✅ normalize column names (old vs new compatibility)
        if "prediction" in df.columns and "final_label" not in df.columns:
            df["final_label"] = df["prediction"]

        if "probability" in df.columns and "phishing_probability" not in df.columns:
            df["phishing_probability"] = df["probability"]

        baseline_data = df.to_dict(orient="records")

    return render_template(
        "dashboard.html",
        baseline_data=baseline_data,
        model=model
    )

# =======================
# soc ALERTS
# =======================

@app.route("/soc")
def soc():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    model = request.args.get("model", "baseline")
    user_data_dir = os.path.join("data", "user_data", user_id)
    csv_path = os.path.join(user_data_dir, MODEL_FILES.get(model, MODEL_FILES["baseline"]))

    alerts = []
    if os.path.exists(csv_path):
        import pandas as pd
        df = pd.read_csv(csv_path)

    # SOC logic: high-risk phishing emails
        alerts = df[
             (df["final_label"].str.contains("Phishing", na=False)) &
            (df["phishing_probability"] >= 0.85)
        ].sort_values(
            "phishing_probability", ascending=False
        ).to_dict(orient="records")

    total_alerts = len(alerts) 

    return render_template("soc.html", user_id=user_id, alerts=alerts,total_alerts=total_alerts, model=model)


# =======================
# LOGOUT
# =======================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =======================
# HOME REDIRECT
# =======================
@app.route("/")
def home():
    return redirect("/login")


# =======================
# BACKGROUND SYNC
# =======================
def start_background_sync(user_id, email):
    """Start Gmail sync and predictions in a background thread (once per user)."""
    if user_id in user_sync_threads and user_sync_threads[user_id].is_alive():
        return  # already running

    def worker():
        user_data_dir = os.path.join("data", "user_data", user_id)
        while True:
            try:
                print(f"[SYNC] Starting Gmail sync for {email}...")
                sync_gmail_to_csv(user_id)  # incremental sync

                # Run predictions after sync
                print(f"[PREDICT] Running models for {email}...")
                subprocess.run(["python", "src/predict_all.py", user_data_dir], check=False)

                print(f"[SYNC] Waiting 180 seconds before next check...")
                time.sleep(180)
            except Exception as e:
                print(f"[ERROR] Background sync failed: {e}")
                time.sleep(60)  # retry after 1 min if error occurs

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    user_sync_threads[user_id] = thread


# =======================
# RUN APP
# =======================
if __name__ == "__main__":
    app.run(debug=False)