from flask import Flask, render_template
import pandas as pd

app = Flask(__name__)

# -------------------------------------------------
# LOAD PREDICTION RESULTS
# -------------------------------------------------
df = pd.read_csv("data/processed/imap_emails_with_predictions.csv")

# -------------------------------------------------
# ROUTE: DASHBOARD
# ------------------------------------------------
@app.route("/") 
def dashboard():

    total_emails = len(df)
    phishing_count = (df["prediction_label"] == "Phishing").sum()
    legit_count = (df["prediction_label"] == "Legitimate").sum()

    phishing_percent = round((phishing_count / total_emails) * 100, 2)
    legit_percent = round((legit_count / total_emails) * 100, 2)

    # Top phishing emails (highest probability)
    top_phishing = df[df["prediction_label"] == "Phishing"] \
        .sort_values(by="phishing_probability", ascending=False) \
        .head(5)

    return render_template(
        "dashboard.html",
        emails=df.to_dict(orient="records"),
        total_emails=total_emails,
        phishing_percent=phishing_percent,
        legit_percent=legit_percent,
        top_phishing=top_phishing.to_dict(orient="records")
    )

if __name__ == "__main__":
    app.run(debug=True)
