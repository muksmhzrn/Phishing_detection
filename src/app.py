from flask import Flask, render_template
import pandas as pd

app = Flask(__name__)

DATA_PATH = "data/processed/imap_emails_with_predictions.csv"

def load_data():
    df = pd.read_csv(DATA_PATH)

    # Fix NaN safely
    df.fillna("", inplace=True)

    # Ensure probability is float
    df["phishing_probability"] = df["phishing_probability"].astype(float)

    # SOC alert logic
    df["soc_alert"] = df["phishing_probability"] >= 0.7

    # Sort latest first
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date", ascending=False)

    return df


@app.route("/")
def dashboard():
    df = load_data()

    total_emails = len(df)
    phishing_count = (df["final_label"].str.contains("Phishing")).sum()
    legit_count = total_emails - phishing_count

    phishing_percent = round((phishing_count / total_emails) * 100, 2) if total_emails else 0
    legit_percent = round((legit_count / total_emails) * 100, 2) if total_emails else 0

    top_phishing = df[df["final_label"].str.contains("Phishing")] \
        .sort_values("phishing_probability", ascending=False) \
        .head(5)

    soc_alert_count = df[df["soc_alert"]].shape[0]

    return render_template(
        "dashboard.html",
        emails=df.head(20).to_dict(orient="records"),
        top_phishing=top_phishing.to_dict(orient="records"),
        total_emails=total_emails,
        phishing_count=phishing_count,
        legit_count=legit_count,
        phishing_percent=phishing_percent,
        legit_percent=legit_percent,
        soc_alert_count=soc_alert_count
    )


@app.route("/soc")
def soc_view():
    df = load_data()

    soc_alerts = df[df["soc_alert"]].head(20)

    return render_template(
        "soc.html",
        alerts=soc_alerts.to_dict(orient="records"),
        total_alerts=len(soc_alerts)
    )


if __name__ == "__main__":
    app.run(debug=True)
