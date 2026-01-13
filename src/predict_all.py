# src/predict_all.py
import os
import sys
import warnings
import joblib
import pandas as pd
from sklearn.exceptions import (
    InconsistentVersionWarning,
)

warnings.filterwarnings(
    "ignore",
    category=InconsistentVersionWarning,
)
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
)

# ===============================
# THRESHOLDS
# ===============================
PHISHING_THRESHOLD = (
    0.5
)
SOC_THRESHOLD = (
    0.7
)

# ===============================
# MODEL PATHS
# ===============================
BASE_DIR = os.path.dirname(
    os.path.abspath(
        __file__
    )
)
PROJECT_ROOT = os.path.dirname(
    BASE_DIR
)

LOGISTIC_MODEL_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "raw",
    "phishing_email_model.joblib",
)
XGB_MODEL_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "raw",
    "xgboost_phishing_email_model.joblib",
)

# ===============================
# WHITELIST DOMAINS
# ===============================
WHITELIST_DOMAINS = {
    "google.com",
    "accounts.google.com",
    "nepalpolice.gov.np"
    "googlemail.com",
    "samsung-mail.com",
    "googlegroups.com",
    "support.google.com",
    "youtube.com",
    "notifications.google.com",
    "payments.google.com",
    "cloud.google.com",
    "firebase.com",
    "email.tubebuddy.com",
}


# ===============================
# HELPERS
# ===============================
def sanitize_text(
    s,
):
    """Normalize text and remove unusual unicode line terminators (U+2028/U+2029)."""
    if (
        s
        is None
    ):
        return ""
    if not isinstance(
        s,
        str,
    ):
        s = str(
            s
        )
    return (
        s.replace(
            "\u2028",
            "\n",
        )
        .replace(
            "\u2029",
            "\n",
        )
        .replace(
            "\r\n",
            "\n",
        )
        .replace(
            "\r",
            "\n",
        )
    )


def assign_final_label(
    prob,
) -> (
    str
):
    try:
        return (
            "Phishing"
            if float(
                prob
            )
            >= PHISHING_THRESHOLD
            else "Legitimate"
        )
    except Exception:
        return "Legitimate"


def get_sender_domain(
    sender: str,
) -> (
    str
):
    """Extract domain from sender email (handles formats like 'Name <email@domain.com>')."""
    if (
        sender
        is None
    ):
        return ""
    if not isinstance(
        sender,
        str,
    ):
        sender = str(
            sender
        )
    s = (
        sender.lower()
    )

    # If it contains angle brackets, take content inside
    if (
        "<"
        in s
        and ">"
        in s
    ):
        inside = (
            s.split(
                "<",
                1,
            )[
                -1
            ]
            .split(
                ">",
                1,
            )[
                0
            ]
            .strip()
        )
        s = inside

    if (
        "@"
        in s
    ):
        return (
            s.split(
                "@",
                1,
            )[
                -1
            ]
            .strip()
            .strip(
                ">"
            )
            .strip()
        )
    return ""


def ensure_columns(
    df: pd.DataFrame,
) -> (
    pd.DataFrame
):
    """Ensure required columns exist."""
    for col in [
        "uid",
        "mailbox",
        "sender",
        "receiver",
        "subject",
        "body",
        "date",
    ]:
        if (
            col
            not in df.columns
        ):
            df[
                col
            ] = ""
    return df


def prepare_dataset(
    input_csv: str,
) -> (
    pd.DataFrame
):
    """Load CSV and build Email Text safely."""
    try:
        df = pd.read_csv(
            input_csv,
            encoding="utf-8",
            engine="python",
        )
    except UnicodeDecodeError:
        df = pd.read_csv(
            input_csv,
            encoding="latin1",
            engine="python",
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to read CSV '{input_csv}': {e}"
        )

    df = ensure_columns(
        df
    )

    # sanitize key text columns
    df[
        "subject"
    ] = (
        df[
            "subject"
        ]
        .fillna(
            ""
        )
        .apply(
            sanitize_text
        )
    )
    df[
        "body"
    ] = (
        df[
            "body"
        ]
        .fillna(
            ""
        )
        .apply(
            sanitize_text
        )
    )

    # date parsing (safe)
    df[
        "date"
    ] = pd.to_datetime(
        df[
            "date"
        ],
        errors="coerce",
        utc=True,
    )

    df[
        "Email Text"
    ] = (
        df[
            "subject"
        ].astype(
            str
        )
        + " "
        + df[
            "body"
        ].astype(
            str
        )
    )

    # drop empty
    df = df[
        df[
            "Email Text"
        ].str.strip()
        != ""
    ].copy()

    # cleaned_body
    if (
        "cleaned_body"
        not in df.columns
    ):
        df[
            "cleaned_body"
        ] = df[
            "body"
        ].astype(
            str
        )
    else:
        df[
            "cleaned_body"
        ] = (
            df[
                "cleaned_body"
            ]
            .fillna(
                ""
            )
            .apply(
                sanitize_text
            )
        )

    return df


def load_model(
    model_path: str,
    name: str,
):
    if not os.path.exists(
        model_path
    ):
        raise FileNotFoundError(
            f"{name} model not found: {model_path}"
        )
    try:
        model = joblib.load(
            model_path
        )
    except Exception as e:
        raise RuntimeError(
            f"{name} model load failed: {e}"
        )
    if not hasattr(
        model,
        "predict_proba",
    ):
        raise RuntimeError(
            f"{name} model has no predict_proba()"
        )
    return model


def predict_probs(
    model,
    texts: pd.Series,
    name: str,
):
    try:
        probs = model.predict_proba(
            texts
        )[
            :,
            1,
        ]
        return probs
    except Exception as e:
        raise RuntimeError(
            f"{name} prediction failed: {e}"
        )


def apply_whitelist_overrides(
    out: pd.DataFrame,
) -> (
    pd.DataFrame
):
    if (
        "sender"
        not in out.columns
    ):
        out[
            "sender"
        ] = ""
    out[
        "sender_domain"
    ] = out[
        "sender"
    ].apply(
        get_sender_domain
    )
    whitelist_mask = out[
        "sender_domain"
    ].isin(
        WHITELIST_DOMAINS
    )

    out.loc[
        whitelist_mask,
        "final_label",
    ] = "Legitimate"
    out.loc[
        whitelist_mask,
        "phishing_probability",
    ] = 0.0
    out.loc[
        whitelist_mask,
        "soc_alert",
    ] = False
    return out


def run_model(
    model_path: str,
    df: pd.DataFrame,
    out_path: str,
    name: str,
) -> bool:
    try:
        model = load_model(
            model_path,
            name,
        )
        print(
            f"[✓] {name}: model loaded"
        )
    except Exception as e:
        print(
            f"[!] {name}: {e}"
        )
        return False

    try:
        probs = predict_probs(
            model,
            df[
                "Email Text"
            ],
            name,
        )
    except Exception as e:
        print(
            f"[!] {name}: {e}"
        )
        return False

    out = (
        df.copy()
    )
    out[
        "phishing_probability"
    ] = probs
    out[
        "final_label"
    ] = out[
        "phishing_probability"
    ].apply(
        assign_final_label
    )
    out[
        "soc_alert"
    ] = (
        out[
            "phishing_probability"
        ]
        >= SOC_THRESHOLD
    )

    out = apply_whitelist_overrides(
        out
    )

    # sanitize before saving (prevents VSCode "unusual line terminators")
    for col in [
        "subject",
        "body",
        "cleaned_body",
        "Email Text",
    ]:
        if (
            col
            in out.columns
        ):
            out[
                col
            ] = (
                out[
                    col
                ]
                .fillna(
                    ""
                )
                .apply(
                    sanitize_text
                )
            )

    try:
        os.makedirs(
            os.path.dirname(
                out_path
            ),
            exist_ok=True,
        )
        out.to_csv(
            out_path,
            index=False,
            encoding="utf-8",
            lineterminator="\n",
        )
        print(
            f"[✓] {name}: output saved -> {out_path}"
        )
        return True
    except Exception as e:
        print(
            f"[!] {name}: failed to save CSV -> {e}"
        )
        return False


# ===============================
# MAIN
# ===============================
def main():
    if (
        len(
            sys.argv
        )
        < 2
    ):
        print(
            'Usage: python predict_all.py "<user_data_dir>"'
        )
        sys.exit(
            1
        )

    user_dir = (
        sys.argv[
            1
        ]
        .strip()
        .strip(
            '"'
        )
        .strip(
            "'"
        )
    )

    if not os.path.isdir(
        user_dir
    ):
        print(
            f"[!] Invalid directory: {user_dir}"
        )
        sys.exit(
            1
        )

    input_csv = os.path.join(
        user_dir,
        "imap_emails.csv",
    )
    if not os.path.exists(
        input_csv
    ):
        print(
            f"[!] Missing dataset: {input_csv}"
        )
        sys.exit(
            1
        )

    try:
        df = prepare_dataset(
            input_csv
        )
    except Exception as e:
        print(
            f"[!] Dataset prepare failed: {e}"
        )
        sys.exit(
            1
        )

    if (
        df.empty
    ):
        print(
            "[!] No valid emails found in dataset (Email Text empty)."
        )
        sys.exit(
            0
        )

    # Logistic
    run_model(
        LOGISTIC_MODEL_PATH,
        df,
        os.path.join(
            user_dir,
            "imap_emails_with_predictions_logistic.csv",
        ),
        "LOGISTIC",
    )

    # XGBoost (optional)
    try:
        import xgboost  # noqa: F401

        print(
            "[✓] xgboost available"
        )
        run_model(
            XGB_MODEL_PATH,
            df,
            os.path.join(
                user_dir,
                "imap_emails_with_predictions_xgb.csv",
            ),
            "XGBOOST",
        )
    except Exception as e:
        print(
            "[!] XGBOOST skipped:",
            e,
        )


if (
    __name__
    == "__main__"
):
    main()
