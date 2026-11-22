"""LinkedIn publisher using LinkedIn's official API (OAuth 2.0 "Connect with LinkedIn").

Setup (once): create an app at https://developer.linkedin.com, add the products
"Sign In with LinkedIn using OpenID Connect" and "Share on LinkedIn", and add the redirect URL
http://localhost:8787/api/connections/linkedin/callback (use your dashboard address).
Then paste the Client ID and Secret on the dashboard's Connections tab and click Connect.

Posts support text plus 1 image, or 2-20 images (multi-image post).
"""

import re
import secrets
import time
from pathlib import Path
from urllib.parse import quote, urlencode

import requests

from .. import connections
from ..config import env

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
API = "https://api.linkedin.com"
SCOPES = "openid profile w_member_social"
DEFAULT_VERSION = "202610"  # LinkedIn-Version header (YYYYMM); override with publish.linkedin.api_version
MAX_CHARS = 3000

_pending_states: dict[str, float] = {}


# ------------------------------------------------------------------ OAuth
def redirect_uri(base_url: str) -> str:
    return base_url.rstrip("/") + "/api/connections/linkedin/callback"


def auth_url(base_url: str) -> str:
    client_id = env("LINKEDIN_CLIENT_ID")
    if not client_id:
        raise RuntimeError("Add your LinkedIn Client ID and Secret first")
    state = secrets.token_urlsafe(24)
    _pending_states[state] = time.time()
    return AUTH_URL + "?" + urlencode({
        "response_type": "code", "client_id": client_id,
        "redirect_uri": redirect_uri(base_url), "state": state, "scope": SCOPES,
    })


def finish_auth(code: str, state: str, base_url: str) -> dict:
    created = _pending_states.pop(state, None)
    if not created or time.time() - created > 900:
        raise RuntimeError("Login link expired or invalid. Click Connect again.")
    r = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": redirect_uri(base_url),
        "client_id": env("LINKEDIN_CLIENT_ID"), "client_secret": env("LINKEDIN_CLIENT_SECRET"),
    }, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"LinkedIn token exchange failed: {r.text[:300]}")
    tok = r.json()
    me = requests.get(f"{API}/v2/userinfo", headers={"Authorization": f"Bearer {tok['access_token']}"},
                      timeout=30)
    me.raise_for_status()
    profile = me.json()
    info = {
        "access_token": tok["access_token"],
        "expires_at": int(time.time()) + int(tok.get("expires_in", 0)),
        "person_urn": f"urn:li:person:{profile['sub']}",
        "name": profile.get("name", ""),
    }
    connections.set_oauth("linkedin", info)
    return info


def status() -> dict:
    info = connections.get_oauth("linkedin")
    if not info.get("access_token"):
        return {"connected": False}
    days = int((info.get("expires_at", 0) - time.time()) / 86400)
    return {"connected": days > 0, "name": info.get("name"), "days_left": max(days, 0)}


def disconnect() -> None:
    connections.set_oauth("linkedin", None)


def _token() -> tuple[str, str]:
    token = env("LINKEDIN_ACCESS_TOKEN")
    urn = env("LINKEDIN_PERSON_URN")
    if token and urn:
        return token, urn
    info = connections.get_oauth("linkedin")
    if not info.get("access_token"):
        raise RuntimeError("LinkedIn is not connected (dashboard → Connections → Connect LinkedIn)")
    if info.get("expires_at", 0) < time.time():
        raise RuntimeError("LinkedIn login expired (they last 60 days). Click Connect again.")
    return info["access_token"], info["person_urn"]


# ------------------------------------------------------------- formatting
_RESERVED = re.compile(r"([\\|{}@\[\]()<>*_~])")


def to_little_text(text: str) -> str:
    """LinkedIn 'commentary' uses a markup where some characters are reserved.
    Escape them, and turn #words into real hashtags."""
    parts = re.split(r"(#\w+)", text)
    out = []
    for part in parts:
        if re.fullmatch(r"#\w+", part):
            out.append("{hashtag|\\#|" + part[1:] + "}")
        else:
            out.append(_RESERVED.sub(r"\\\1", part).replace("#", "\\#"))
    return "".join(out)


# ---------------------------------------------------------------- publish
def _headers(token: str, version: str) -> dict:
    return {"Authorization": f"Bearer {token}", "LinkedIn-Version": version,
            "X-Restli-Protocol-Version": "2.0.0", "Content-Type": "application/json"}


def _upload_image(path: str, token: str, owner: str, version: str) -> str:
    r = requests.post(f"{API}/rest/images?action=initializeUpload", headers=_headers(token, version),
                      json={"initializeUploadRequest": {"owner": owner}}, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"LinkedIn image upload init failed ({r.status_code}): {r.text[:300]}")
    value = r.json()["value"]
    up = requests.put(value["uploadUrl"], data=Path(path).read_bytes(),
                      headers={"Authorization": f"Bearer {token}"}, timeout=120)
    if up.status_code >= 400:
        raise RuntimeError(f"LinkedIn image upload failed ({up.status_code})")
    return value["image"]


VIDEO_MAX_BYTES = 500 * 1024 * 1024


def _upload_video(path: str, token: str, owner: str, version: str) -> str:
    """Multi-part upload via the Videos API. Returns the video URN."""
    p = Path(path)
    size = p.stat().st_size
    if size > VIDEO_MAX_BYTES:
        raise RuntimeError("LinkedIn videos must be under 500 MB")
    r = requests.post(f"{API}/rest/videos?action=initializeUpload", headers=_headers(token, version), timeout=30,
                      json={"initializeUploadRequest": {"owner": owner, "fileSizeBytes": size,
                                                        "uploadCaptions": False, "uploadThumbnail": False}})
    if r.status_code >= 400:
        raise RuntimeError(f"LinkedIn video upload init failed ({r.status_code}): {r.text[:300]}")
    value = r.json()["value"]
    etags = []
    with open(p, "rb") as f:
        for part in value["uploadInstructions"]:
            f.seek(part["firstByte"])
            chunk = f.read(part["lastByte"] - part["firstByte"] + 1)
            up = requests.put(part["uploadUrl"], data=chunk, timeout=600,
                              headers={"Content-Type": "application/octet-stream"})
            if up.status_code >= 400:
                raise RuntimeError(f"LinkedIn video part upload failed ({up.status_code})")
            etags.append(up.headers.get("ETag", "").strip('"'))
    fin = requests.post(f"{API}/rest/videos?action=finalizeUpload", headers=_headers(token, version), timeout=60,
                        json={"finalizeUploadRequest": {"video": value["video"], "uploadToken": value.get("uploadToken", ""),
                                                        "uploadedPartIds": etags}})
    if fin.status_code >= 400:
        raise RuntimeError(f"LinkedIn video finalize failed ({fin.status_code}): {fin.text[:300]}")
    # Wait (up to ~3 min) for LinkedIn to process the video before posting.
    for _ in range(36):
        s = requests.get(f"{API}/rest/videos/{quote(value['video'], safe='')}", headers=_headers(token, version), timeout=30)
        state = s.json().get("status") if s.ok else None
        if state == "AVAILABLE":
            break
        if state == "PROCESSING_FAILED":
            raise RuntimeError("LinkedIn could not process this video (check format: MP4, 3 s - 30 min)")
        time.sleep(5)
    return value["video"]


def publish(post: dict, opts: dict) -> str:
    token, urn = _token()
    version = str(opts.get("api_version") or DEFAULT_VERSION)
    body = post["body"]
    if post.get("kind") == "video":
        body = (post.get("meta") or {}).get("linkedin_text") or post["body"]
    elif post.get("kind") != "social":  # blog post shared to LinkedIn: teaser + link
        link = next(iter((post.get("published") or {}).values()), "")
        body = f"{post['title']}\n\n{post.get('subtitle', '')}\n\n{link}".strip()
    if len(body) > MAX_CHARS:
        body = body[: MAX_CHARS - 1] + "…"

    payload = {
        "author": urn,
        "commentary": to_little_text(body),
        "visibility": opts.get("visibility", "PUBLIC"),
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    media = [m for m in (post.get("media") or []) if Path(m["path"]).exists()]
    video = next((m for m in media if m.get("type") == "video"), None)
    if video:
        payload["content"] = {"media": {"id": _upload_video(video["path"], token, urn, version),
                                        "title": post["title"][:200]}}
    else:
        images = [{"id": _upload_image(m["path"], token, urn, version), "altText": m.get("alt", "")[:120]}
                  for m in media[:20]]
        if len(images) == 1:
            payload["content"] = {"media": images[0]}
        elif len(images) > 1:
            payload["content"] = {"multiImage": {"images": images}}

    r = requests.post(f"{API}/rest/posts", headers=_headers(token, version), json=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"LinkedIn returned {r.status_code}: {r.text[:300]}")
    post_urn = r.headers.get("x-restli-id", "")
    return f"https://www.linkedin.com/feed/update/{post_urn}/" if post_urn else "https://www.linkedin.com/feed/"
