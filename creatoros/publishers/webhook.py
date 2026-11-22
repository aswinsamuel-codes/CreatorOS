"""Custom platforms: send posts to any webhook / API URL.

Works with automation tools (Zapier, Make, n8n, IFTTT, Pipedream) to reach almost any app
(Instagram, Facebook, X, Threads, Discord, Slack, WordPress...), or with an app's own API.

Payload (JSON):
{
  "source": "CreatorOS", "test": false, "post_id": 12, "kind": "blog|social|video",
  "title": "...", "text": "<ready-to-post text>", "description": "<long text / blog body>",
  "tags": ["..."], "hashtags": ["#..."], "link": "<first published URL, if any>",
  "media": [{"type": "image|video", "filename": "...", "mime": "...", "alt": "...", "data_base64": "..."}]
}
If the response is JSON with a "url" field, that URL is shown as the post link.
"""

import base64
import mimetypes
from pathlib import Path

import requests

from .. import connections

MAX_INLINE_BYTES = 25 * 1024 * 1024


def _headers(spec: dict) -> dict:
    h = {"Content-Type": "application/json", "User-Agent": "CreatorOS"}
    if spec.get("api_key"):
        h[spec.get("auth_header") or "Authorization"] = spec["api_key"]
    return h


def build_payload(post: dict, send_media: bool = True) -> dict:
    meta = post.get("meta") or {}
    text = meta.get("linkedin_text") if post.get("kind") == "video" else post.get("body", "")
    if post.get("kind") == "blog":
        text = f"{post['title']}\n\n{post.get('subtitle', '')}".strip()
    media, budget = [], MAX_INLINE_BYTES
    for m in post.get("media") or []:
        p = Path(m["path"])
        item = {"type": m.get("type", "image"), "filename": p.name,
                "mime": mimetypes.guess_type(p.name)[0] or "application/octet-stream", "alt": m.get("alt", "")}
        if send_media and p.exists() and p.stat().st_size <= budget:
            item["data_base64"] = base64.b64encode(p.read_bytes()).decode()
            budget -= p.stat().st_size
        media.append(item)
    return {
        "source": "CreatorOS", "test": False, "post_id": post.get("id"), "kind": post.get("kind", "blog"),
        "title": post.get("title", ""), "text": text or post.get("body", ""), "description": post.get("body", ""),
        "tags": post.get("tags") or [], "hashtags": ["#" + t.replace(" ", "") for t in post.get("tags") or []],
        "link": next(iter((post.get("published") or {}).values()), ""), "media": media,
    }


def send(spec: dict, payload: dict) -> requests.Response:
    r = requests.request(spec.get("method", "POST"), spec["url"], json=payload, headers=_headers(spec), timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"{spec.get('name', 'Webhook')} returned {r.status_code}: {r.text[:200]}")
    return r


def publish_custom(cid: str, post: dict) -> str:
    spec = connections.list_custom().get(cid)
    if not spec:
        raise RuntimeError(f"Custom platform '{cid}' not found (Connections tab)")
    r = send(spec, build_payload(post, spec.get("send_media", True)))
    try:
        url = r.json().get("url")
    except ValueError:
        url = None
    return url or f"sent to {spec['name']}"


def test_custom(cid: str) -> str:
    spec = connections.list_custom().get(cid)
    if not spec:
        raise RuntimeError("Not found")
    send(spec, {"source": "CreatorOS", "test": True, "title": "Test", "text": "Test message from CreatorOS ✅",
                "media": []})
    return f"{spec['name']} accepted the test message"
