import re
from email.header import decode_header
from typing import Optional


def safe_decode_header(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        parts = decode_header(value)
        out = []
        for text, enc in parts:
            if isinstance(text, bytes):
                out.append(text.decode(enc or "utf-8", errors="replace"))
            else:
                out.append(str(text))
        return "".join(out).strip()
    except Exception:
        return str(value).strip()


def strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?>.*?(</\1>)", " ", html)
    text = re.sub(r"(?is)<.*?>", " ", html)
    text = (
        text.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u200b", " ").replace("\ufeff", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text