import imaplib
import email
from email.header import decode_header
import csv
import socket
import os
from dotenv import load_dotenv

from email_utils import extract_urls, clean_urls, clean_email_body

socket.setdefaulttimeout(30)
load_dotenv()

IMAP_SERVER = os.getenv("IMAP_SERVER")
USERNAME = os.getenv("USRNAME")
PASSWORD = os.getenv("PASSWORD")

OUTPUT_FILE = "data/processed/email_dataset.csv"

MAILBOXES = [
    '"[Gmail]/All Mail"',   # FIXED (quoted)
    '"[Gmail]/Spam"'        # FIXED (quoted)
]


def decode_text(value):
    if not value:
        return ""
    decoded, enc = decode_header(value)[0]
    if isinstance(decoded, bytes):
        return decoded.decode(enc or "utf-8", errors="ignore")
    return decoded


def connect():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(USERNAME, PASSWORD)
    print("[✓] Connected to Gmail IMAP")
    return mail


def extract_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                body += payload.decode(charset, errors="ignore")
    else:
        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
    return body


def build_dataset():
    mail = connect()
    os.makedirs("data/processed", exist_ok=True)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

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

        for mailbox in MAILBOXES:
            print(f"[+] Reading mailbox: {mailbox}")
            mail.select(mailbox)

            status, messages = mail.search(None, "ALL")
            email_ids = messages[0].split()

            print(f"    → {len(email_ids)} emails found")

            for eid in email_ids:
                _, data = mail.fetch(eid, "(RFC822)")
                msg = email.message_from_bytes(data[0][1])

                sender = msg.get("From", "")
                receiver = msg.get("To", "")
                date = msg.get("Date", "")
                subject = decode_text(msg.get("Subject", ""))

                raw_body = extract_body(msg)
                urls = clean_urls(extract_urls(raw_body))
                cleaned_body = clean_email_body(raw_body)

                writer.writerow([
                    mailbox.replace('"', ""),  # clean name in CSV
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

    print(f"\n[✓] Dataset successfully saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    build_dataset()
