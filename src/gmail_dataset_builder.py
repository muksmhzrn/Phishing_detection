import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import csv
import socket
import os
from dotenv import load_dotenv

from email_utils import extract_urls, clean_urls, clean_email_body

# -------------------------------------------------
# BASIC SETUP
# -------------------------------------------------
socket.setdefaulttimeout(30)
load_dotenv()

IMAP_SERVER = os.getenv("IMAP_SERVER")
USERNAME = os.getenv("USRNAME")
PASSWORD = os.getenv("PASSWORD")

OUTPUT_FILE = "data/processed/email_dataset.csv"
MESSAGE_ID_FILE = "data/processed/seen_message_ids.txt"

MAILBOXES = {
    "INBOX": "Inbox",
    "[Gmail]/Spam": "Spam"
}

# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def decode_text(value):
    if not value:
        return ""
    decoded, enc = decode_header(value)[0]
    if isinstance(decoded, bytes):
        return decoded.decode(enc or "utf-8", errors="ignore")
    return decoded


def normalize_date(date_str):
    try:
        return parsedate_to_datetime(date_str).isoformat()
    except:
        return ""


def connect():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(USERNAME, PASSWORD)
    print("[✓] Connected to Gmail IMAP")
    return mail


def extract_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="ignore")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="ignore")
    return body.strip()


def load_seen_message_ids():
    if not os.path.exists(MESSAGE_ID_FILE):
        return set()
    with open(MESSAGE_ID_FILE, "r") as f:
        return set(line.strip() for line in f.readlines())


def save_seen_message_ids(ids):
    with open(MESSAGE_ID_FILE, "w") as f:
        for mid in ids:
            f.write(mid + "\n")


# -------------------------------------------------
# MAIN INGESTION
# -------------------------------------------------
def build_dataset():
    os.makedirs("data/processed", exist_ok=True)

    seen_message_ids = load_seen_message_ids()
    new_message_ids = set()

    file_exists = os.path.exists(OUTPUT_FILE)

    mail = connect()

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow([
                "mailbox",
                "sender",
                "receiver",
                "date",
                "subject",
                "body",
                "cleaned_body",
                "urls",
                "num_urls",
                "body_length",
                "label"
            ])

        for mailbox, label in MAILBOXES.items():
            print(f"[+] Checking {label}")
            mail.select(mailbox)

            status, data = mail.search(None, "ALL")
            if status != "OK":
                continue

            email_ids = data[0].split()
            added = 0

            for eid in email_ids:
                _, msg_data = mail.fetch(eid, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])

                message_id = msg.get("Message-ID", "").strip()

                # 🚫 HARD DEDUPLICATION (FIXES SPAM LOOP)
                if not message_id or message_id in seen_message_ids:
                    continue

                sender = msg.get("From", "")
                receiver = msg.get("To", "")
                date = normalize_date(msg.get("Date", ""))
                subject = decode_text(msg.get("Subject", ""))

                raw_body = extract_body(msg)
                cleaned_body = clean_email_body(raw_body)
                urls = clean_urls(extract_urls(raw_body))

                writer.writerow([
                    label,
                    sender,
                    receiver,
                    date,
                    subject,
                    raw_body,
                    cleaned_body,
                    ",".join(urls),
                    len(urls),
                    len(cleaned_body.split()),
                    ""
                ])

                new_message_ids.add(message_id)
                added += 1

            print(f"    → {added} new emails added")

    save_seen_message_ids(seen_message_ids.union(new_message_ids))
    print("\n[✓] Gmail ingestion completed safely")


# -------------------------------------------------
# ENTRY POINT
# -------------------------------------------------
if __name__ == "__main__":
    build_dataset()