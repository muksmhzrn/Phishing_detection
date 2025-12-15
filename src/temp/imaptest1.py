import imaplib



try:
    # Connect to Gmail IMAP server using SSL
    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)

    # Login using app password
    mail.login(EMAIL, APP_PASSWORD)
    print("✅ IMAP login successful")

    # Select inbox
    status, messages = mail.select("INBOX")
    print("📥 Inbox selected")

    # Get total number of emails
    status, data = mail.search(None, "ALL")
    email_count = len(data[0].split())
    print(f"📧 Total emails in inbox: {email_count}")

    # Logout
    mail.logout()
    print("🚪 Logged out successfully")

except imaplib.IMAP4.error as e:
    print("❌ IMAP login failed")
    print("Error:", e)
