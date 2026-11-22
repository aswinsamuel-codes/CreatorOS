"""YouTube publisher using the official YouTube Data API v3 with Google OAuth ("Connect YouTube").

Setup (once): Google Cloud console → create a project → enable "YouTube Data API v3" →
OAuth consent screen (External, add yourself as a test user) → Credentials → OAuth client ID
(type "Web application") with redirect URI http://localhost:8787/api/connections/youtube/callback.
Paste the Client ID and Secret on the dashboard's Connections tab and click Connect.

Note: until a Google Cloud project passes YouTube's API audit, videos uploaded through the
API are locked to **private**. You can make them public in YouTube Studio, or apply for an audit.
"""

import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

from .. import connections
from ..config import env, log

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"
CHUNK = 8 * 1024 * 1024  # must be a multiple of 256 KiB

_pending_states: dict[str, float] = {}


def redirect_uri(base_url: str) -> str:
    return base_url.rstrip("/") + "/api/connections/youtube/callback"


def auth_url(base_url: str) -> str:
    client_id = env("YOUTUBE_CLIENT_ID")
    if not client_id:
        raise RuntimeError("Add your Google OAuth Client ID and Secret first")
    state = secrets.token_urlsafe(24)
    _pending_states[state] = time.time()
    return AUTH_URL + "?" + urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri(base_url),
        "scope": SCOPES, "state": state, "access_type": "offline", "prompt": "consent",
        "include_granted_scopes": "true",
    })


def finish_auth(code: str, state: str, base_url: str) -> dict:
    created = _pending_states.pop(state, None)
    if not created or time.time() - created > 900:
        raise RuntimeError("Login link expired or invalid. Click Connect again.")
    r = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(base_url),
        "client_id": env("YOUTUBE_CLIENT_ID"), "client_secret": env("YOUTUBE_CLIENT_SECRET"),
    }, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"Google token exchange failed: {r.text[:300]}")
    tok = r.json()
    info = {"access_token": tok["access_token"], "refresh_token": tok.get("refresh_token", ""),
            "expires_at": int(time.time()) + int(tok.get("expires_in", 3600)) - 60}
    ch = requests.get(f"{API}/channels", params={"part": "snippet", "mine": "true"},
                      headers={"Authorization": f"Bearer {info['access_token']}"}, timeout=30)
    items = ch.json().get("items", []) if ch.ok else []
    info["channel"] = items[0]["snippet"]["title"] if items else "YouTube"
    info["channel_id"] = items[0]["id"] if items else ""
    connections.set_oauth("youtube", info)
    return info


def status() -> dict:
    info = connections.get_oauth("youtube")
    if not info.get("access_token"):
        return {"connected": False}
    return {"connected": bool(info.get("refresh_token")) or info.get("expires_at", 0) > time.time(),
            "name": info.get("channel", "YouTube")}


def disconnect() -> None:
    connections.set_oauth("youtube", None)


def _token() -> str:
    info = connections.get_oauth("youtube")
    if not info.get("access_token"):
        raise RuntimeError("YouTube is not connected (dashboard → Connections → Connect YouTube)")
    if info.get("expires_at", 0) > time.time():
        return info["access_token"]
    if not info.get("refresh_token"):
        raise RuntimeError("YouTube login expired. Click Connect again.")
    r = requests.post(TOKEN_URL, data={
        "grant_type": "refresh_token", "refresh_token": info["refresh_token"],
        "client_id": env("YOUTUBE_CLIENT_ID"), "client_secret": env("YOUTUBE_CLIENT_SECRET"),
    }, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"YouTube token refresh failed (reconnect YouTube): {r.text[:200]}")
    tok = r.json()
    info.update(access_token=tok["access_token"], expires_at=int(time.time()) + int(tok.get("expires_in", 3600)) - 60)
    connections.set_oauth("youtube", info)
    return info["access_token"]


def publish(post: dict, opts: dict) -> str:
    video = next((m for m in post.get("media") or [] if m.get("type") == "video"), None)
    if not video:
        raise RuntimeError("This post has no video to upload to YouTube")
    path = Path(video["path"])
    if not path.exists():
        raise RuntimeError(f"Video file not found: {path}")
    yt = (post.get("meta") or {}).get("youtube", {})
    token = _token()
    size = path.stat().st_size
    body = {
        "snippet": {"title": post["title"][:100], "description": post.get("body", "")[:5000],
                    "tags": post.get("tags") or [], "categoryId": str(yt.get("category_id") or opts.get("category_id") or "28")},
        "status": {"privacyStatus": yt.get("privacy") or opts.get("privacy", "private"),
                   "selfDeclaredMadeForKids": False},
    }
    init = requests.post(
        UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"}, json=body, timeout=60,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/*", "X-Upload-Content-Length": str(size)},
    )
    if init.status_code >= 400:
        raise RuntimeError(f"YouTube rejected the upload ({init.status_code}): {init.text[:300]}")
    session = init.headers["Location"]

    result = None
    with open(path, "rb") as f:
        offset = 0
        while offset < size:
            chunk = f.read(CHUNK)
            end = offset + len(chunk) - 1
            for attempt in range(5):
                try:
                    r = requests.put(session, data=chunk, timeout=600, headers={
                        "Authorization": f"Bearer {token}", "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {offset}-{end}/{size}"})
                except requests.RequestException as e:
                    log.warning("YouTube upload chunk failed (%s), retrying", e)
                    time.sleep(2 ** attempt)
                    continue
                if r.status_code in (500, 502, 503, 504):
                    time.sleep(2 ** attempt)
                    continue
                break
            else:
                raise RuntimeError("YouTube upload failed after several retries")
            if r.status_code in (200, 201):
                result = r.json()
                break
            if r.status_code != 308:
                raise RuntimeError(f"YouTube upload error ({r.status_code}): {r.text[:300]}")
            offset = end + 1
            log.info("YouTube upload %d%%", int(offset * 100 / size))
    if not result:
        raise RuntimeError("YouTube upload did not complete")
    video_id = result["id"]

    thumb = video.get("thumb")
    if thumb and Path(thumb).exists() and opts.get("upload_thumbnail", True):
        t = requests.post("https://www.googleapis.com/upload/youtube/v3/thumbnails/set",
                          params={"videoId": video_id}, data=Path(thumb).read_bytes(), timeout=120,
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"})
        if not t.ok:  # custom thumbnails need a verified channel; not fatal
            log.info("Thumbnail not set (%s): %s", t.status_code, t.text[:150])
    short = yt.get("short")
    return f"https://youtube.com/shorts/{video_id}" if short else f"https://youtu.be/{video_id}"
