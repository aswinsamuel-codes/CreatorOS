"""DEV Community (dev.to) publisher."""

import re

import requests

from ..config import env


def publish(post: dict, opts: dict) -> str:
    key = env("DEVTO_API_KEY")
    if not key:
        raise RuntimeError("DEVTO_API_KEY is not set in .env")
    tags = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in post.get("tags", [])]
    article = {
        "title": post["title"],
        "body_markdown": post["body"],
        "published": bool(opts.get("published", False)),
        "tags": [t for t in tags if t][:4],
        "description": post.get("subtitle", "")[:250],
    }
    if opts.get("canonical_url_from_medium") and post.get("published", {}).get("medium"):
        article["canonical_url"] = post["published"]["medium"]
    r = requests.post(
        "https://dev.to/api/articles",
        json={"article": article},
        headers={"api-key": key, "Content-Type": "application/json", "Accept": "application/vnd.forem.api-v1+json"},
        timeout=60,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"dev.to returned {r.status_code}: {r.text[:300]}")
    return r.json().get("url", "")
