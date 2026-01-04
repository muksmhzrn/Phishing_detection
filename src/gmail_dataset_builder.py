import imaplib
import email
import pandas as pd
import os
import time
import threading
from auth import get_user_gmail_credentials

DATA_DIR = "data/user_data"
SYNC_INTERVAL = 60  # seconds


def fetch_emails_from_gmail(user_email, app_password, csv_path):
    """Fetch new emails from Gmail and append to CSV safely."""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user_email, app_password)
        mail.select("inbox")

        # --------------------------------
        # Load existing emails safely
        # --------------------------------
        if os.path.exists(csv_path):
            df_existing = pd.read_csv(csv_path)

            if "uid" in df_existing.columns and not df_existing.empty:
                df_existing["uid"] = pd.to_numeric(df_existing["uid"], errors="coerce")
                df_existing.dropna(subset=["uid"], inplace=True)
                df_existing["uid"] = df_existing["uid"].astype(int)
                last_uid = int(df_existing["uid"].max())
            else:
                df_existing = pd.DataFrame()
                last_uid = None
        else:
            df_existing = pd.DataFrame()
            last_uid = None

        # --------------------------------
        # Search Gmail
        # --------------------------------
        if last_uid is not None:
            result, data = mail.uid("search", None, f"(UID {last_uid + 1}:*)")
        else:
            result, data = mail.uid("search", None, "ALL")

        if result != "OK":
            print(f"[SYNC] Failed to search emails for {user_email}")
            return

        uids = data[0].split()
        if not uids:
            print(f"[SYNC] No new emails for {user_email}")
            return

        emails_list = []

        # --------------------------------
        # Fetch messages
        # --------------------------------
        for uid in uids:
            result, msg_data = mail.uid("fetch", uid, "(RFC822)")
            if result != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = email.header.decode_header(msg.get("Subject"))[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode(errors="ignore")

            from_ = msg.get("From")
            to_ = msg.get("To")
            date_ = msg.get("Date")

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if (
                        part.get_content_type() == "text/plain"
                        and part.get_content_disposition() in (None, "inline")
                    ):
                        try:
                            body += part.get_payload(decode=True).decode(errors="ignore")
                        except:
                            pass
            else:
                try:
                    body = msg.get_payload(decode=True).decode(errors="ignore")
                except:
                    pass

            emails_list.append({
                "uid": int(uid),
                "mailbox": "inbox",
                "sender": from_,
                "receiver": to_,
                "subject": subject,
                "body": body,
                "date": date_,
            })

        # --------------------------------
        # Save CSV
        # --------------------------------
        if emails_list:
            df_new = pd.DataFrame(emails_list)

            if not df_existing.empty:
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_combined = df_new

            df_combined.drop_duplicates(subset=["uid"], inplace=True)
            df_combined.sort_values(by="uid", inplace=True)

            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            df_combined.to_csv(csv_path, index=False)

            print(f"[SYNC] {len(df_new)} new emails saved for {user_email}")

        mail.logout()

    except Exception as e:
        print(f"[SYNC] Error fetching emails for {user_email}: {e}")


def sync_gmail_to_csv(user_id):
    """Background Gmail sync thread per user."""
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

    thread = threading.Thread(target=background_sync, daemon=True)
    thread.start()

    print(f"[SYNC] Background Gmail sync started for user {user_email}")
