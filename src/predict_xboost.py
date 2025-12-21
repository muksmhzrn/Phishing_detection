# =========================================================
# PHISHING & SPAM DETECTION USING XGBOOST MODEL
# =========================================================

import pandas as pd
import joblib

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
MODEL_PATH = "data/processed/fxgboost_phishing_email_model.joblib"
EMAILS_CSV_PATH = "data/processed/email_dataset.csv"
OUTPUT_PATH = "data/processed/imap_emails_with_predictions_xgb.csv"

PHISHING_THRESHOLD = 0.5

# ---------------------------------------------------------
# LOAD MODEL
# ---------------------------------------------------------
model = joblib.load(MODEL_PATH)
print("✅ XGBoost phishing model loaded")

# ---------------------------------------------------------
# LOAD EMAIL DATA
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

df = df[df["Email Text"].str.strip() != ""].copy()

# ---------------------------------------------------------
# SORT BY LATEST EMAILS FIRST
# ---------------------------------------------------------
if "date" in df.columns:
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values(by="date", ascending=False)

# ---------------------------------------------------------
# PREDICTION
# ---------------------------------------------------------
df["phishing_probability"] = model.predict_proba(
    df["Email Text"]
)[:, 1]

# ---------------------------------------------------------
# BASE LABEL
# ---------------------------------------------------------
df["prediction_label"] = df["phishing_probability"].apply(
    lambda x: "Phishing" if x >= PHISHING_THRESHOLD else "Legitimate"
)

# ---------------------------------------------------------
# SPAM-AWARE FINAL LABEL
# ---------------------------------------------------------
def assign_final_label(row):
    mailbox = str(row["mailbox"]).lower()
    prob = row["phishing_probability"]

    if "spam" in mailbox and prob >= PHISHING_THRESHOLD:
        return "Spam-Phishing"
    elif "spam" in mailbox:
        return "Spam"
    elif prob >= PHISHING_THRESHOLD:
        return "Phishing"
    else:
        return "Legitimate"

df["final_label"] = df.apply(assign_final_label, axis=1)

# ---------------------------------------------------------
# ALERT FLAG (SOC)
# ---------------------------------------------------------
df["alert"] = df["phishing_probability"] >= PHISHING_THRESHOLD

# ---------------------------------------------------------
# DISPLAY LATEST 5 PREDICTIONS
# ---------------------------------------------------------
print("\n🔍 Latest 5 predictions (XGBoost):")
print(df[[
    "mailbox",
    "subject",
    "final_label",
    "phishing_probability",
    "alert"
]].head(5))

# ---------------------------------------------------------
# DISPLAY LATEST PHISHING EMAILS
# ---------------------------------------------------------
latest_phishing = df[df["final_label"].isin(["Phishing", "Spam-Phishing"])].head(10)

print("\n🚨 Latest Phishing Emails (XGBoost):")
print(latest_phishing[[
    "mailbox",
    "subject",
    "phishing_probability"
]])

# ---------------------------------------------------------
# SAVE RESULTS
# ---------------------------------------------------------
df.to_csv(OUTPUT_PATH, index=False)
print(f"\n✅ XGBoost results saved to: {OUTPUT_PATH}")
