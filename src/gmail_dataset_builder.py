import imaplib
import email
import csv
import os

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

CSV_FILE = "imap_email.csv"
STATE_FILE = "last_uid.txt"


def sync_gmail_to_csv(user_email: str, app_password: str, user_dir: str):
    os.makedirs(user_dir, exist_ok=True)

    csv_path = os.path.join(user_dir, CSV_FILE)
    state_path = os.path.join(user_dir, STATE_FILE)

    last_uid = 0
    if os.path.exists(state_path):
        try:
            last_uid = int(open(state_path).read().strip())
        except:
            last_uid = 0

    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    mail.login(user_email, app_password)

    new_rows = []

    for mailbox in ["INBOX", "[Gmail]/Spam"]:
        mail.select(mailbox)

        if last_uid == 0:
            status, data = mail.uid("search", None, "ALL")
        else:
            status, data = mail.uid("search", None, f"UID {last_uid + 1}:*")

        if status != "OK" or not data or not data[0]:
            continue

        for uid in data[0].split():
            status, msg_data = mail.uid("fetch", uid, "(RFC822)")
            if status != "OK":
                continue

            msg = email.message_from_bytes(msg_data[0][1])

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            new_rows.append({
                "uid": int(uid),
                "mailbox": mailbox,
                "sender": msg.get("From", ""),
                "subject": msg.get("Subject", ""),
                "date": msg.get("Date", ""),
                "body": body
            })

            last_uid = max(last_uid, int(uid))

    mail.logout()

    if new_rows:
        write_header = not os.path.exists(csv_path)
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["uid", "mailbox", "sender", "subject", "date", "body"]
            )
            if write_header:
                writer.writeheader()
            writer.writerows(new_rows)

    with open(state_path, "w") as f:
        f.write(str(last_uid))
