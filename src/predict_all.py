import os
import sys
import pandas as pd
import joblib
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

PHISHING_THRESHOLD = 0.5
SOC_THRESHOLD = 0.7

# Paths to models
LOGISTIC_MODEL_PATH = "data/raw/phishing_email_model.joblib"     # baseline logistic model
XGB_MODEL_PATH = "data/raw/xgboost_phishing_email_model.joblib"  # xgboost model


def assign_final_label(prob: float) -> str:
    """Convert probability to Phishing / Legitimate label"""
    return "Phishing" if float(prob) >= PHISHING_THRESHOLD else "Legitimate"


def prepare_dataset(input_csv: str) -> pd.DataFrame:
    """Load and preprocess dataset for prediction"""
    df = pd.read_csv(input_csv)

    # Ensure columns exist
    for col in ["subject", "body", "date"]:
        if col not in df.columns:
            df[col] = ""

    # Convert date safely
    df["date"] = pd.to_datetime(df.get("date"), errors="coerce", utc=True)

    # Combine subject + body as text
    df["Email Text"] = df["subject"].fillna("").astype(str) + " " + df["body"].fillna("").astype(str)
    df = df[df["Email Text"].str.strip() != ""].copy()

    # Add cleaned_body for dashboard display
    if "cleaned_body" not in df.columns:
        df["cleaned_body"] = df["body"].fillna("").astype(str)

    return df


def run_model(model_path: str, df: pd.DataFrame, out_path: str, name: str) -> bool:
    """Load model, predict probabilities, assign labels, save CSV"""
    if not os.path.exists(model_path):
        print(f"[!] {name}: model not found -> {model_path}")
        return False

    try:
        model = joblib.load(model_path)
        print(f"[✓] {name}: model loaded -> {model_path}")
    except Exception as e:
        print(f"[!] {name}: failed to load model -> {e}")
        return False

    try:
        probs = model.predict_proba(df["Email Text"])[:, 1]
    except Exception as e:
        print(f"[!] {name}: predict_proba failed -> {e}")
        return False

    out = df.copy()
    out["phishing_probability"] = probs
    out["final_label"] = out["phishing_probability"].apply(assign_final_label)
    out["soc_alert"] = out["phishing_probability"] >= SOC_THRESHOLD

    out.to_csv(out_path, index=False)
    print(f"[✓] {name}: predictions saved -> {out_path}")
    return True


def main():
    if len(sys.argv) < 2:
        print('Usage: python predict_all.py "user_data_dir"')
        sys.exit(1)

    output_dir = sys.argv[1].strip()
    if not os.path.isdir(output_dir):
        print(f"[!] user_data_dir not found: {output_dir}")
        sys.exit(1)

    input_csv = os.path.join(output_dir, "imap_emails.csv")
    if not os.path.exists(input_csv):
        print(f"[!] Dataset not found: {input_csv}")
        sys.exit(1)

    df = prepare_dataset(input_csv)

    # Logistic model predictions
    logistic_out = os.path.join(output_dir, "imap_emails_with_predictions_logistic.csv")
    run_model(LOGISTIC_MODEL_PATH, df, logistic_out, "LOGISTIC")

    # XGBoost predictions
    try:
        import xgboost
        print("[✓] xgboost import OK:", xgboost.__version__)
    except Exception as e:
        print("[!] xgboost import FAILED:", repr(e))
        return

    xgb_out = os.path.join(output_dir, "imap_emails_with_predictions_xgb.csv")
    run_model(XGB_MODEL_PATH, df, xgb_out, "XGBOOST")


if __name__ == "__main__":
    main()