# =========================================================
# PHISHING DETECTION USING TRAINED MODEL (JOBLIB)
# =========================================================

import pandas as pd
import joblib

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
# MODEL_PATH = "pphishing_email_model.joblib"
MODEL_PATH = "phishing_email_model.joblib"
EMAILS_CSV_PATH = "email_dataset.csv"
OUTPUT_PATH = "imap_emails_with_predictions.csv"

# ---------------------------------------------------------
# LOAD TRAINED MODEL
# ---------------------------------------------------------
model = joblib.load(MODEL_PATH)
print("✅ Trained phishing model loaded")

# ---------------------------------------------------------
# LOAD IMAP EMAILS CSV
# ---------------------------------------------------------
df = pd.read_csv(EMAILS_CSV_PATH)
print(f"📧 Emails loaded: {df.shape[0]}")

# ---------------------------------------------------------
# CREATE EMAIL TEXT (MUST MATCH TRAINING)
# ---------------------------------------------------------
df["Email Text"] = (
    df["subject"].fillna("") + " " +
    df["body"].fillna("")
)

# Remove empty emails
df = df[df["Email Text"].str.strip() != ""].copy()

# ---------------------------------------------------------
# PREDICT PHISHING / LEGITIMATE
# ---------------------------------------------------------
df["prediction"] = model.predict(df["Email Text"])

# Convert numeric labels to readable text
df["prediction_label"] = df["prediction"].map({
    0: "Legitimate",
    1: "Phishing"
})

# ---------------------------------------------------------
# PREDICTION CONFIDENCE (PROBABILITY)
# ---------------------------------------------------------
df["phishing_probability"] = model.predict_proba(
    df["Email Text"]
)[:, 1]

# ---------------------------------------------------------
# OPTIONAL: ALERT THRESHOLD (SOC-STYLE)
# ---------------------------------------------------------
df["alert"] = df["phishing_probability"] >= 0.7

# ---------------------------------------------------------
# DISPLAY SAMPLE RESULTS
# ---------------------------------------------------------
print("\n🔍 Sample predictions:")
print(df[[
    "subject",
    "prediction_label",
    "phishing_probability",
    "alert"
]].head())

# ---------------------------------------------------------
# SAVE RESULTS TO CSV
# ---------------------------------------------------------
df.to_csv(OUTPUT_PATH, index=False)
print(f"\n✅ Results saved to: {OUTPUT_PATH}")
