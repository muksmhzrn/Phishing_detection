# =========================================================
# PHISHING & SPAM DETECTION USING TRAINED MODEL
# =========================================================

import pandas as pd
import joblib

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
MODEL_PATH = "data/processed/phishing_email_model.joblib"
EMAILS_CSV_PATH = "data/processed/email_dataset.csv"
OUTPUT_PATH = "data/processed/imap_emails_with_predictions.csv"

PHISHING_THRESHOLD = 0.5

# ---------------------------------------------------------
# LOAD TRAINED MODEL
# ---------------------------------------------------------
model = joblib.load(MODEL_PATH)
print("✅ Trained phishing model loaded")

# ---------------------------------------------------------
# LOAD EMAIL DATASET
# ---------------------------------------------------------
df = pd.read_csv(EMAILS_CSV_PATH)
print(f"📧 Emails loaded: {df.shape[0]}")

# ---------------------------------------------------------
# CREATE EMAIL TEXT (MATCH TRAINING)
# ---------------------------------------------------------
df["Email Text"] = (
    df["subject"].fillna("") + " " +
    df["body"].fillna("")
)

df = df[df["Email Text"].str.strip() != ""].copy()

# ---------------------------------------------------------
# PHISHING PREDICTION
# ---------------------------------------------------------
df["prediction"] = model.predict(df["Email Text"])

df["phishing_probability"] = model.predict_proba(
    df["Email Text"]
)[:, 1]

# ---------------------------------------------------------
# PHISHING LABEL
# ---------------------------------------------------------
df["prediction_label"] = df["phishing_probability"].apply(
    lambda x: "Phishing" if x >= PHISHING_THRESHOLD else "Legitimate"
)

# ---------------------------------------------------------
# SPAM-AWARE FINAL LABEL
# ---------------------------------------------------------
def assign_final_label(row):
    mailbox = str(row["mailbox"]).lower()

    if "spam" in mailbox and row["phishing_probability"] >= PHISHING_THRESHOLD:
        return "Spam-Phishing"
    elif "spam" in mailbox:
        return "Spam"
    elif row["phishing_probability"] >= PHISHING_THRESHOLD:
        return "Phishing"
    else:
        return "Legitimate"


df["final_label"] = df.apply(assign_final_label, axis=1)

# ---------------------------------------------------------
# ALERT FLAG
# ---------------------------------------------------------
df["alert"] = df["phishing_probability"] >= PHISHING_THRESHOLD

# ---------------------------------------------------------
# DISPLAY SAMPLE
# ---------------------------------------------------------
print("\n🔍 Sample predictions:")
print(df[[
    "mailbox",
    "subject",
    "final_label",
    "phishing_probability",
    "alert"
]].head())

# ---------------------------------------------------------
# SAVE RESULTS
# ---------------------------------------------------------
df.to_csv(OUTPUT_PATH, index=False)
print(f"\n✅ Results saved to: {OUTPUT_PATH}")
