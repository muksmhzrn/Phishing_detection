import imaplib
import email
import pandas as pd
import os
import time
import threading
from auth import get_user_gmail_credentials

# =========================
# CONFIG
# =========================
IMAP_SERVER = "imap.gmail.com"
DATA_DIR = "data/user_data"
SYNC_INTERVAL = 60  # seconds

MAILBOXES = {
    "inbox": "INBOX",
    "spam": "[Gmail]/Spam"
}

# =========================
# FETCH EMAILS (PER MAILBOX)
# =========================
def fetch_emails_from_mailbox(mail, mailbox_name, label, last_uid):
    emails = []

    mail.select(mailbox_name)

    if last_uid is not None:
        result, data = mail.uid("search", None, f"(UID {last_uid + 1}:*)")
    else:
        result, data = mail.uid("search", None, "ALL")

    if result != "OK" or not data or not data[0]:
        return emails

    uids = data[0].split()

    for uid in uids:
        result, msg_data = mail.uid("fetch", uid, "(RFC822)")
        if result != "OK":
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        # ---- HEADERS ----
        subject = email.header.decode_header(msg.get("Subject"))[0][0]
        if isinstance(subject, bytes):
            subject = subject.decode(errors="ignore")

        sender = msg.get("From")
        receiver = msg.get("To")
        date_ = msg.get("Date")

        # ---- BODY ----
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and part.get_content_disposition() in (None, "inline"):
                    try:
                        body += part.get_payload(decode=True).decode(errors="ignore")
                    except:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode(errors="ignore")
            except:
                pass

        emails.append({
            "uid": int(uid),
            "mailbox": label,
            "sender": sender,
            "receiver": receiver,
            "subject": subject,
            "body": body,
            "date": date_,
        })

    return emails

# =========================
# MAIN GMAIL FETCH
# =========================
def fetch_emails_from_gmail(user_email, app_password, csv_path):
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(user_email, app_password)

        # -------------------------
        # LOAD EXISTING CSV
        # -------------------------
        if os.path.exists(csv_path):
            df_existing = pd.read_csv(csv_path)
        else:
            df_existing = pd.DataFrame()

        # -------------------------
        # LAST UID PER MAILBOX
        # -------------------------
        last_uids = {}
        for label in MAILBOXES.keys():
            if not df_existing.empty and "uid" in df_existing.columns:
                df_m = df_existing[df_existing["mailbox"] == label]
                last_uids[label] = int(df_m["uid"].max()) if not df_m.empty else None
            else:
                last_uids[label] = None

        all_new_emails = []

        # -------------------------
        # FETCH EACH MAILBOX
        # -------------------------
        for label, mailbox in MAILBOXES.items():
            print(f"[SYNC] {label.upper()} last UID = {last_uids[label]}")
            emails = fetch_emails_from_mailbox(
                mail,
                mailbox,
                label,
                last_uids[label]
            )
            all_new_emails.extend(emails)

        if not all_new_emails:
            print(f"[SYNC] No new emails for {user_email}")
            mail.logout()
            return

        df_new = pd.DataFrame(all_new_emails)

        # -------------------------
        # MERGE (NEW FIRST)
        # -------------------------
        if not df_existing.empty:
            df_combined = pd.concat([df_new, df_existing], ignore_index=True)
        else:
            df_combined = df_new

        # Deduplicate (UID + mailbox)
        df_combined.drop_duplicates(
            subset=["uid", "mailbox"],
            keep="first",
            inplace=True
        )

        df_combined.sort_values(by="uid", ascending=False, inplace=True)
        df_combined.reset_index(drop=True, inplace=True)

        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        df_combined.to_csv(csv_path, index=False)

        print(f"[SYNC] {len(df_new)} new emails saved for {user_email}")

        mail.logout()

    except Exception as e:
        print(f"[SYNC] Error fetching emails for {user_email}: {e}")

# =========================
# BACKGROUND SYNC LOOP
# =========================
def sync_gmail_to_csv(user_id):
    creds = get_user_gmail_credentials(user_id)
    if not creds:
        print(f"[SYNC] No credentials found for user {user_id}")
        return

    user_email = creds.get("email")
    app_password = creds.get("app_password")

    user_dir = os.path.join(DATA_DIR, user_id)
    os.makedirs(user_dir, exist_ok=True)

    csv_path = os.path.join(user_dir, "imap_emails.csv")

    def background_sync():
        while True:
            try:
                print(f"[SYNC] Checking Gmail for new emails for user {user_id}...")
                fetch_emails_from_gmail(user_email, app_password, csv_path)
            except Exception as e:
                print(f"[SYNC] Background sync failed: {e}")
            time.sleep(SYNC_INTERVAL)

    threading.Thread(target=background_sync, daemon=True).start()
    print(f"[SYNC] Background Gmail sync started for user {user_email}")
