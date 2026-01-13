from flask import Flask, render_template, request, redirect, session
from auth import register_user, login_user, get_user_gmail_credentials, login_required
from gmail_dataset_builder import sync_gmail_to_csv
from database import init_db
import subprocess, threading, os, time, sys
import pandas as pd
from predict_all import SOC_THRESHOLD

print("PYTHON EXECUTABLE:", sys.executable)

# =======================
# APP SETUP
# =======================
app = Flask(__name__)
app.secret_key = "supersecretkey"




MODEL_FILES = {
    "baseline": "imap_emails_with_predictions_logistic.csv",
    "xgboost": "imap_emails_with_predictions_xgb.csv"
}

# Track background sync threads
user_sync_threads = {}

# =======================
# REGISTRATION
# =======================
@app.route("/register", methods=["GET", "POST"])
def register():
    error = success = None

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
            start_background_sync(user_id, email)
            return redirect("/dashboard")
        else:
            error = "Invalid email or password"

    return render_template("login.html", error=error)

# # =======================
# DASHBOARD
# =======================
@app.route("/dashboard")
@login_required
def dashboard():
    page = int(request.args.get("page", 1))
    PER_PAGE = 20

    user_id = session["user_id"]
    creds = get_user_gmail_credentials(user_id)
    user_email = creds.get("email") if creds else "Unknown"

    model = request.args.get("model", "baseline")
    label_filter = request.args.get("filter", "all")

    user_data_dir = os.path.join("data", "user_data", user_id)
    csv_path = os.path.join(user_data_dir, MODEL_FILES.get(model))

    # defaults (SAFE)
    emails = []
    total_emails = legit_count = phishing_count = 0
    top_phishing = []
    filtered_total = total_pages = 1
    start = end = 0
    soc_alerts_count = 0

    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            df = pd.DataFrame()

        if not df.empty:
            # ======================
            # NORMALIZE COLUMNS
            # ======================
            if "prediction" in df.columns and "final_label" not in df.columns:
                df["final_label"] = df["prediction"]

            if "probability" in df.columns and "phishing_probability" not in df.columns:
                df["phishing_probability"] = df["probability"]

            # ensure required columns exist
            for col in ["final_label", "phishing_probability"]:
                if col not in df.columns:
                    df[col] = ""

            df["phishing_probability"] = pd.to_numeric(
                df["phishing_probability"], errors="coerce"
            ).fillna(0.0)

            # ======================
            # FULL DATASET (NO FILTER)
            # ======================
            df_all = df.copy()

            total_emails = len(df_all)
            legit_count = df_all["final_label"].str.contains("Legit", na=False).sum()
            phishing_count = df_all["final_label"].str.contains("Phishing", na=False).sum()

            phishing_count = int(phishing_count)
            legit_count = int(legit_count)
            total_emails = int(total_emails)    

            # SOC alerts count (GLOBAL)
            soc_alerts_count = (
                (df_all["final_label"].str.contains("Phishing", na=False)) &
                (df_all["phishing_probability"] >= 0.85)
            ).sum()

            # TOP PHISHING (GLOBAL)
            top_phishing = (
                df_all[df_all["final_label"].str.contains("Phishing", na=False)]
                .sort_values("phishing_probability", ascending=False)
                .head(5)
                .to_dict(orient="records")
            )

            # ======================
            # APPLY FILTER FOR TABLE ONLY
            # ======================
            if label_filter == "legit":
                df = df[df["final_label"].str.contains("Legit", na=False)]
            elif label_filter == "phishing":
                df = df[df["final_label"].str.contains("Phishing", na=False)]

            # ======================
            # PAGINATION
            # ======================
            filtered_total = len(df)
            total_pages = max(1, (filtered_total + PER_PAGE - 1) // PER_PAGE)

            start = (page - 1) * PER_PAGE
            end = start + PER_PAGE
            emails = df.iloc[start:end].to_dict(orient="records")

            # ======================
            # SIMPLE PHISHING ALERT
            # ======================
            show_phishing_alert = False
            new_phishing_count = 0

            # ENSURE PYTHON INT (CRITICAL)
            phishing_count = int(phishing_count)

            prev_count = session.get("prev_phishing_count")

            if prev_count is None:
                session["prev_phishing_count"] = phishing_count
            else:
                prev_count = int(prev_count)

                if phishing_count > prev_count:
                    show_phishing_alert = True
                    new_phishing_count = phishing_count - prev_count
                    session["prev_phishing_count"] = phishing_count

    return render_template(
        "dashboard.html",
        user_email=user_email,
        user_id=user_id,
        emails=emails,
        model=model,
        label_filter=label_filter,
        total_emails=total_emails,
        legit_count=legit_count,
        phishing_count=phishing_count,
        soc_alerts_count=int(soc_alerts_count),
        top_phishing=top_phishing,
        page=page,
        total_pages=total_pages,
        filtered_total=filtered_total,
        showing_from=start + 1 if filtered_total else 0,
        showing_to=min(end, filtered_total),
        show_phishing_alert=show_phishing_alert,
        new_phishing_count=new_phishing_count,
    )

# =======================
# SOC ALERTS
# =======================
@app.route("/soc")
@login_required
def soc():
    user_id = session["user_id"]
    model = request.args.get("model", "baseline")
    page = int(request.args.get("page", 1))

    PER_PAGE = 10
    WINDOW = 4

    user_data_dir = os.path.join("data", "user_data", user_id)
    csv_path = os.path.join(user_data_dir, MODEL_FILES.get(model))

    alerts = []

    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)

        if "prediction" in df.columns and "final_label" not in df.columns:
            df["final_label"] = df["prediction"]

        if "probability" in df.columns and "phishing_probability" not in df.columns:
            df["phishing_probability"] = df["probability"]

        # SOC = high-risk phishing
        df = df[
            (df["final_label"].str.contains("Phishing", na=False)) &
            (df["phishing_probability"] >= 0.85)
        ].sort_values("phishing_probability", ascending=False)

        total_alerts = len(df)
        total_pages = max(1, (total_alerts + PER_PAGE - 1) // PER_PAGE)

        start = (page - 1) * PER_PAGE
        end = start + PER_PAGE

        alerts = df.iloc[start:end].to_dict(orient="records")
    else:
        total_alerts = 0
        total_pages = 1
        start = end = 0

    creds = get_user_gmail_credentials(user_id)
    user_email = creds.get("email") if creds else "Unknown"

    return render_template(
        "soc.html",
        alerts=alerts,
        total_alerts=total_alerts,
        model=model,
        user_email=user_email,

        # ✅ REQUIRED FOR TEMPLATE
        page=page,
        total_pages=total_pages,
        window=WINDOW,
        showing_from=start + 1 if total_alerts else 0,
        showing_to=min(end, total_alerts)
    )


# =======================
# LOGOUT
# =======================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# =======================
# HOME
# =======================
@app.route("/")
def home():
    return redirect("/login")

# =======================
# BACKGROUND SYNC
# =======================
def start_background_sync(user_id, email):
    if user_id in user_sync_threads and user_sync_threads[user_id].is_alive():
        return

    def worker():
        user_data_dir = os.path.join("data", "user_data", user_id)
        while True:
            try:
                print(f"[SYNC] Gmail sync for {email}")
                sync_gmail_to_csv(user_id)

                print(f"[PREDICT] Running models for {email}")
                subprocess.run(
                    ["python", "src/predict_all.py", user_data_dir],
                    check=False
                )

                time.sleep(20)
            except Exception as e:
                print(f"[ERROR] Background sync failed: {e}")
                time.sleep(60)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    user_sync_threads[user_id] = thread

# =======================
# RUN
# =======================
if __name__ == "__main__":
    app.run(debug=False)