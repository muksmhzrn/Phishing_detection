from flask import Flask, render_template, request, redirect, session
from auth import register_user, login_user, get_user_gmail_credentials
from gmail_dataset_builder import sync_gmail_to_csv
import subprocess, threading, os, time

app = Flask(__name__)
app.secret_key = "supersecretkey"  # for session

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
def dashboard():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    # Start background sync if not already running
    user_email = get_user_gmail_credentials(user_id).get("email")
    start_background_sync(user_id, user_email)

    creds = get_user_gmail_credentials(user_id)
    emails_csv = os.path.join("data", "user_data", user_id, "imap_emails_with_predictions.csv")
    return render_template("dashboard.html", user_id=user_id, user_email=user_email, emails_csv=emails_csv)


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
