import re
from bs4 import BeautifulSoup

TRACKING_DOMAINS = [
    "customeriomail.com",
    "googleusercontent.com",
    "doubleclick.net",
    "gravatar.com",
    "amazonaws.com"
]

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")


def extract_urls(text):
    return re.findall(r"https?://\\S+", text)


def clean_urls(urls):
    final = []
    for url in urls:
        url = url.strip().replace('"', "").replace("'", "")
        if url.endswith(IMAGE_EXTENSIONS):
            continue
        if any(d in url for d in TRACKING_DOMAINS):
            continue
        if len(url) < 10:
            continue
        final.append(url)
    return list(set(final))


def clean_email_body(raw_text):
    soup = BeautifulSoup(raw_text, "html.parser")
    text = soup.get_text(separator=" ")
    text = re.sub(r"https?://\\S+", "", text)
    text = re.sub(r"\\s+", " ", text).strip()
    return text
