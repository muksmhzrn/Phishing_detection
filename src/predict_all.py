# =========================================================
# PHISHING DETECTION – BASELINE + XGBOOST (SOC READY)
# =========================================================

import pandas as pd
import joblib
import sys
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
BASE_MODEL_PATH = "data/raw/phishing_email_model.joblib"
XGB_MODEL_PATH = "data/raw/fxgboost_phishing_email_model.joblib"

EMAILS_CSV = "data/processed/email_dataset.csv"

BASE_OUTPUT = "data/processed/imap_emails_with_predictions.csv"
XGB_OUTPUT = "data/processed/imap_emails_with_predictions_xgb.csv"


PHISHING_THRESHOLD = 0.5

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def assign_final_label(row):
    prob = row["phishing_probability"]

    if prob >= PHISHING_THRESHOLD:
        return "Phishing"
    else:
        return "Legitimate"


def prepare_dataset():
    df = pd.read_csv(EMAILS_CSV)

    df["date"] = pd.to_datetime(df.get("date"), errors="coerce", utc=True)

    df["Email Text"] = (
        df["subject"].fillna("") + " " + df["body"].fillna("")
    )

    df = df[df["Email Text"].str.strip() != ""].copy()
    df = df.sort_values(by="date", ascending=False)

    return df


# ---------------------------------------------------------
# BASELINE MODEL
# ---------------------------------------------------------
print("\n Running Baseline Model")

df_base = prepare_dataset()

base_model = joblib.load(BASE_MODEL_PATH)
print(" Baseline model loaded")

df_base["phishing_probability"] = base_model.predict_proba(
    df_base["Email Text"]
)[:, 1]

df_base["final_label"] = df_base.apply(assign_final_label, axis=1)
df_base["alert"] = df_base["phishing_probability"] >= PHISHING_THRESHOLD

df_base.to_csv(BASE_OUTPUT, index=False)
print(f" Baseline results saved → {BASE_OUTPUT}")

print("\n  Latest 5 tested emails (Baseline):")
print(df_base[[
    "mailbox",
    "subject",
    "final_label",
    "phishing_probability",
    "alert"
]].head(5))


# ---------------------------------------------------------
# XGBOOST MODEL
# ---------------------------------------------------------
print("\n Running XGBoost Model")

try:
    import xgboost
except ImportError:
    print(" xgboost not installed. Skipping XGBoost predictions.")
    sys.exit(0)

df_xgb = prepare_dataset()

xgb_model = joblib.load(XGB_MODEL_PATH)
print(" XGBoost model loaded")

df_xgb["phishing_probability"] = xgb_model.predict_proba(
    df_xgb["Email Text"]
)[:, 1]

df_xgb["final_label"] = df_xgb.apply(assign_final_label, axis=1)
df_xgb["alert"] = df_xgb["phishing_probability"] >= PHISHING_THRESHOLD

df_xgb.to_csv(XGB_OUTPUT, index=False)
print(f" XGBoost results saved → {XGB_OUTPUT}")

print("\n Latest 5 tested emails (XGBoost):")
print(df_xgb[[
    "mailbox",
    "subject",
    "final_label",
    "phishing_probability",
    "alert"
]].head(5))

print("\n Latest SOC Alerts (XGBoost):")
print(
    df_xgb[df_xgb["alert"] == True][[
        "mailbox",
        "subject",
        "phishing_probability"
    ]].head(5)
)

print("\n Prediction pipeline completed successfully")
