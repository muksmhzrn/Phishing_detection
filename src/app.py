from flask import Flask, render_template, request
import pandas as pd
import threading
import time
import os

app = Flask(__name__)

BASELINE_PATH = "data/processed/imap_emails_with_predictions.csv"
XGB_PATH = "data/processed/imap_emails_with_predictions_xgb.csv"


def background_updater():
    while True:
        print("[*] Running background update...")
        os.system("python src/gmail_dataset_builder.py")
        os.system("python src/predict_all.py")
        time.sleep(60)  # 2 minutes


def load_data(model_type):
    path = BASELINE_PATH if model_type == "baseline" else XGB_PATH
    df = pd.read_csv(path)

    # ---- FIX: handle text and numeric columns separately ----
    text_cols = ["mailbox", "sender", "receiver", "subject", "body", "final_label"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("")

    if "phishing_probability" in df.columns:
        df["phishing_probability"] = pd.to_numeric(
            df["phishing_probability"], errors="coerce"
        ).fillna(0.0)

    # ---- Date handling ----
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    df = df.sort_values("date", ascending=False)

    # ---- SOC alert logic ----
    df["soc_alert"] = df["phishing_probability"] >= 0.7

    return df



@app.route("/")
def dashboard():
    model = request.args.get("model", "baseline")
    df = load_data(model)

    total = len(df)
    phishing = df["final_label"].str.contains("Phishing").sum()
    legit = total - phishing

    top_phishing = (
        df[df["final_label"].str.contains("Phishing")]
        .sort_values("phishing_probability", ascending=False)
        .head(5)
    )

    return render_template(
        "dashboard.html",
        model=model,
        emails=df.to_dict(orient="records"),
        top_phishing=top_phishing.to_dict(orient="records"),
        total_emails=total,
        phishing_count=phishing,
        legit_count=legit,
        soc_alert_count=df["soc_alert"].sum()
    )


@app.route("/soc")
def soc():
    model = request.args.get("model", "baseline")
    df = load_data(model)
    alerts = df[df["soc_alert"]]

    return render_template(
        "soc.html",
        alerts=alerts.to_dict(orient="records"),
        total_alerts=len(alerts),
        model=model
    )


if __name__ == "__main__":
    print("[✓] Starting background updater thread")
    updater = threading.Thread(target=background_updater, daemon=True)
    updater.start()

    print("[✓] Starting Flask server")
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )
