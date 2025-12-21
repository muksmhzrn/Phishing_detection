from flask import Flask, render_template, request
import pandas as pd

app = Flask(__name__)

BASELINE_PATH = "data/processed/imap_emails_with_predictions.csv"
XGB_PATH = "data/processed/imap_emails_with_predictions_xgb.csv"


# =========================
# LOAD DATA BASED ON MODEL
# =========================
def load_data(model):
    if model == "xgboost":
        path = XGB_PATH
    else:
        path = BASELINE_PATH  # default = baseline

    df = pd.read_csv(path)

    # Clean data
    df.fillna("", inplace=True)
    df["phishing_probability"] = df["phishing_probability"].astype(float)

    # Date sorting
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date", ascending=False)

    # SOC alert flag
    df["soc_alert"] = df["phishing_probability"] >= 0.7

    return df


# =========================
# DASHBOARD
# =========================
@app.route("/")
def dashboard():
    model = request.args.get("model", "baseline")

    df = load_data(model)

    total_emails = len(df)
    phishing_count = df["final_label"].str.contains("Phishing").sum()
    legit_count = total_emails - phishing_count

    top_phishing = (
        df[df["final_label"].str.contains("Phishing")]
        .sort_values("phishing_probability", ascending=False)
        .head(5)
    )

    soc_alert_count = df["soc_alert"].sum()

    return render_template(
        "dashboard.html",
        model=model,
        emails=df.to_dict(orient="records"),
        top_phishing=top_phishing.to_dict(orient="records"),
        total_emails=total_emails,
        phishing_count=phishing_count,
        legit_count=legit_count,
        soc_alert_count=soc_alert_count
    )


# =========================
# SOC VIEW
# =========================
@app.route("/soc")
def soc_view():
    model = request.args.get("model", "baseline")

    df = load_data(model)
    alerts = df[df["soc_alert"]]

    return render_template(
        "soc.html",
        alerts=alerts.to_dict(orient="records"),
        total_alerts=len(alerts),
        model=model
    )


# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    app.run(debug=True)
