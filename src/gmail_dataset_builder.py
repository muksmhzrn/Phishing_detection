import imaplib
import email
import csv
import os
import ssl

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993


def sync_gmail_to_csv(email_addr, app_password, csv_path):
    """
    Pulls emails from Gmail Inbox and Spam.
    - If CSV does not exist → pulls all emails
    - If CSV exists → pulls only new emails
    - Never crashes the app
    """

    try:
        context = ssl.create_default_context()

        mail = imaplib.IMAP4_SSL(
            IMAP_HOST,
            IMAP_PORT,
            ssl_context=context,
            timeout=15
        )

        mail.login(email_addr, app_password)

        last_uid = 0
        rows = []

        # Load existing data if present
        if os.path.exists(csv_path):
            with open(csv_path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
                if rows:
                    last_uid = int(rows[-1]["uid"])

        for folder in ["INBOX", "[Gmail]/Spam"]:
            mail.select(folder)
            status, data = mail.uid("search", None, "ALL")
            if status != "OK":
                continue

            for uid in data[0].split():
                uid = int(uid)
                if uid <= last_uid:
                    continue

                _, msg_data = mail.uid("fetch", str(uid), "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])

                subject = msg.get("Subject", "")
                sender = msg.get("From", "")
                date = msg.get("Date", "")
                body = ""

                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="ignore")
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors="ignore")

                rows.append({
                    "uid": uid,
                    "folder": folder,
                    "from": sender,
                    "subject": subject,
                    "body": body,
                    "date": date,
                    "prediction": ""
                })

        mail.logout()

        os.makedirs(os.path.dirname(csv_path), exist_ok=True)

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["uid", "folder", "from", "subject", "body", "date", "prediction"]
            )
            writer.writeheader()
            writer.writerows(rows)

    except Exception as e:
        # VERY IMPORTANT: never crash Flask
        print(f"[IMAP WARNING] Gmail sync skipped: {e}")
