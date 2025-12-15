from flask import Flask, render_template
import pandas as pd

app = Flask(__name__)

CSV_PATH = "data/processed/imap_emails_with_predictions.csv"

@app.route("/")
def dashboard():
    df = pd.read_csv(CSV_PATH)

    # Fix missing columns safely
    df["sender"] = df.get("sender", "")
    df["date"] = df.get("date", "")
    df["cleaned_body"] = df.get("cleaned_body", "")
    df["prediction_label"] = df.get("prediction_label", "")
    df["phishing_probability"] = df.get("phishing_probability", 0)

    # Convert date for sorting
    df["parsed_date"] = pd.to_datetime(df["date"], errors="coerce")

    # Sort latest first
    df = df.sort_values(by="parsed_date", ascending=False)

    # Counts
    total_emails = len(df)
    phishing_count = (df["prediction_label"] == "Phishing").sum()
    legit_count = (df["prediction_label"] == "Legitimate").sum()

    phishing_percent = round((phishing_count / total_emails) * 100, 2) if total_emails else 0
    legit_percent = round((legit_count / total_emails) * 100, 2) if total_emails else 0

    # Top phishing emails
    top_phishing = (
        df[df["prediction_label"] == "Phishing"]
        .sort_values(by="phishing_probability", ascending=False)
        .head(5)
        .to_dict(orient="records")
    )

    emails = df.to_dict(orient="records")

    return render_template(
        "dashboard.html",
        emails=emails,
        top_phishing=top_phishing,
        total_emails=total_emails,
        phishing_count=phishing_count,
        legit_count=legit_count,
        phishing_percent=phishing_percent,
        legit_percent=legit_percent
    )

if __name__ == "__main__":
    app.run(debug=True)
