"""Fetch the readable text of a source article."""

import requests
from bs4 import BeautifulSoup

from ...config import log

UA = {"User-Agent": "Mozilla/5.0 (compatible; CreatorOS/0.1)"}


def fetch_text(url: str, max_chars: int = 12000) -> str:
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        if "html" not in r.headers.get("Content-Type", "html"):
            return ""
    except Exception as e:
        log.warning("Could not fetch %s: %s", url, e)
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    paras = [p.get_text(" ", strip=True) for p in root.find_all(["p", "h2", "h3", "li"])]
    text = "\n".join(p for p in paras if len(p) > 40)
    return text[:max_chars]
