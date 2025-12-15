import re
from bs4 import BeautifulSoup

TRACKING_DOMAINS = [
    "customeriomail.com",
    "googleusercontent.com",
    "doubleclick.net",
    "gravatar.com",
    "amazonaws.com",
    "mailchimp.com",
    "sendgrid.net"
]

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")


def extract_urls(text):
    urls = set()

    if not text:
        return []

    # 1️⃣ Extract normal URLs
    urls.update(re.findall(r"https?://[^\s\"'>]+", text))

    # 2️⃣ Extract href URLs from HTML
    soup = BeautifulSoup(text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http"):
            urls.add(href)

    return list(urls)


def clean_urls(urls):
    final_urls = []

    for url in urls:
        url = url.strip().replace('"', "").replace("'", "")

        if url.lower().endswith(IMAGE_EXTENSIONS):
            continue

        if any(domain in url for domain in TRACKING_DOMAINS):
            continue

        if len(url) < 10:
            continue

        final_urls.append(url)

    return list(set(final_urls))


def clean_email_body(raw_text):
    if not raw_text:
        return ""

    soup = BeautifulSoup(raw_text, "html.parser")
    text = soup.get_text(separator=" ")

    # remove URLs from body
    text = re.sub(r"https?://[^\s]+", "", text)

    # normalize spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text
