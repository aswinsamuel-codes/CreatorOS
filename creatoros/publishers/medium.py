"""Medium publisher (uses a Medium integration token)."""

import requests

from ..config import env

API = "https://api.medium.com/v1"


def _headers() -> dict:
    token = env("MEDIUM_TOKEN")
    if not token:
        raise RuntimeError("MEDIUM_TOKEN is not set in .env")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Charset": "utf-8",
    }


def me() -> dict:
    r = requests.get(f"{API}/me", headers=_headers(), timeout=20)
    if r.status_code == 401:
        raise RuntimeError("Medium rejected the token (401). Check MEDIUM_TOKEN.")
    r.raise_for_status()
    return r.json()["data"]


def publish(post: dict, opts: dict) -> str:
    user = me()
    # Medium doesn't render the title field, so the title goes in the content too.
    content = f"# {post['title']}\n\n"
    if post.get("subtitle"):
        content += f"*{post['subtitle']}*\n\n"
    content += post["body"]
    body = {
        "title": post["title"][:100],
        "contentFormat": "markdown",
        "content": content,
        "tags": [t[:25] for t in post.get("tags", [])][:5],
        "publishStatus": opts.get("publish_status", "draft"),
        "notifyFollowers": bool(opts.get("notify_followers", False)),
    }
    r = requests.post(f"{API}/users/{user['id']}/posts", json=body, headers=_headers(), timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"Medium returned {r.status_code}: {r.text[:300]}")
    return r.json()["data"]["url"]
