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
SYNC_INTERVAL = 20  # seconds

MAILBOXES = {
    "inbox": "INBOX",
    "spam": "[Gmail]/Spam"
}

# =========================
# FETCH EMAILS (PER MAILBOX UID SAFE)
# =========================
def fetch_emails_from_mailbox(mail, mailbox_name, label, last_uid):
    emails = []

    status, _ = mail.select(mailbox_name)
    if status != "OK":
        print(f"[IMAP] Cannot open {mailbox_name}")
        return emails, last_uid

    if last_uid:
        result, data = mail.uid("search", None, f"(UID {last_uid + 1}:*)")
    else:
        result, data = mail.uid("search", None, "ALL")

    if result != "OK" or not data or not data[0]:
        return emails, last_uid

    for uid in data[0].split():
        uid = int(uid)

        result, msg_data = mail.uid("fetch", str(uid), "(RFC822)")
        if result != "OK":
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = email.header.decode_header(msg.get("Subject"))[0][0]
        if isinstance(subject, bytes):
            subject = subject.decode(errors="ignore")

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
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
            "uid": uid,
            "mailbox": label,
            "sender": msg.get("From"),
            "receiver": msg.get("To"),
            "subject": subject,
            "body": body,
            "date": msg.get("Date"),
        })

        last_uid = max(last_uid or 0, uid)

    return emails, last_uid


# =========================
# MAIN GMAIL FETCH
# =========================
def fetch_emails_from_gmail(user_email, app_password, csv_path):
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(user_email, app_password)

        # Load existing data
        if os.path.exists(csv_path):
            df_existing = pd.read_csv(csv_path)
        else:
            df_existing = pd.DataFrame()

        # Build last UID map per mailbox
        last_uid_map = {}
        if not df_existing.empty:
            for label in MAILBOXES:
                sub = df_existing[df_existing["mailbox"] == label]
                if not sub.empty:
                    last_uid_map[label] = int(sub["uid"].max())
                else:
                    last_uid_map[label] = None
        else:
            last_uid_map = {label: None for label in MAILBOXES}

        all_new_emails = []

        for label, mailbox in MAILBOXES.items():
            emails, last_uid = fetch_emails_from_mailbox(
                mail, mailbox, label, last_uid_map[label]
            )
            last_uid_map[label] = last_uid
            all_new_emails.extend(emails)

        if not all_new_emails:
            print(f"[SYNC] No new emails for {user_email}")
            mail.logout()
            return

        df_new = pd.DataFrame(all_new_emails)

        # Merge + deduplicate
        if not df_existing.empty:
            df_all = pd.concat([df_new, df_existing], ignore_index=True)
        else:
            df_all = df_new

        df_all.drop_duplicates(subset=["uid", "mailbox"], inplace=True)
        df_all.sort_values("uid", ascending=False, inplace=True)
        df_all.reset_index(drop=True, inplace=True)

        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        df_all.to_csv(csv_path, index=False)

        print(f"[SYNC] {len(df_new)} new emails saved for {user_email}")
        mail.logout()

    except Exception as e:
        print(f"[SYNC] Error fetching emails for {user_email}: {e}")


# =========================
# BACKGROUND THREAD
# =========================
def sync_gmail_to_csv(user_id):
    creds = get_user_gmail_credentials(user_id)
    if not creds:
        print(f"[SYNC] No credentials for user {user_id}")
        return

    user_email = creds["email"]
    app_password = creds["app_password"]

    user_dir = os.path.join(DATA_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)

    csv_path = os.path.join(user_dir, "imap_emails.csv")

    def worker():
        while True:
            fetch_emails_from_gmail(user_email, app_password, csv_path)
            time.sleep(SYNC_INTERVAL)

    threading.Thread(target=worker, daemon=True).start()
    print(f"[SYNC] Gmail sync started for {user_email}")
