"""Platform connections: OAuth tokens and API keys entered in the dashboard.

Stored in data/connections.json (ignored by git). Values in .env always win, so
technical users can keep using .env only.
"""

import json
import threading
from datetime import datetime

from .config import DATA_DIR

STORE = DATA_DIR / "connections.json"
_lock = threading.Lock()

# What the dashboard shows on the Connections tab: a tile per platform, and a guided
# setup window with numbered steps (links open in a new tab) and the boxes to fill in.
PLATFORMS = {
    "claude": {
        "label": "Claude AI", "logo": "✳", "color": "#d97757", "group": "AI brain", "auth": "token", "ai": True,
        "fields": [{"name": "ANTHROPIC_API_KEY", "label": "API key", "placeholder": "sk-ant-…"}],
        "steps": [
            ["Open the Claude Console and sign in", "https://console.anthropic.com/settings/keys"],
            ["Click 'Create Key', give it a name like CreatorOS, and copy it"],
            ["Paste it below and click Save, then Test (Claude needs API credits: console.anthropic.com → Billing)"],
            ["Under 'Use this AI', pick a model and click 'Use for writing' and/or 'Use for picking stories'"],
        ],
    },
    "gemini": {
        "label": "Google Gemini", "logo": "✦", "color": "#4285f4", "group": "AI brain", "auth": "token", "ai": True,
        "fields": [{"name": "GEMINI_API_KEY", "label": "API key", "placeholder": "AIza…"}],
        "steps": [
            ["Open Google AI Studio and sign in with your Google account", "https://aistudio.google.com/apikey"],
            ["Click 'Create API key' (pick or create a project) and copy the key"],
            ["Paste it below and click Save, then Test (Gemini has a free tier with daily limits)"],
            ["Under 'Use this AI', pick a model and click 'Use for writing' and/or 'Use for picking stories'"],
        ],
    },
    "openai": {
        "label": "OpenAI", "logo": "◎", "color": "#10a37f", "group": "AI brain", "auth": "token", "ai": True,
        "fields": [{"name": "OPENAI_API_KEY", "label": "API key", "placeholder": "sk-…"}],
        "steps": [
            ["Open the OpenAI platform and sign in", "https://platform.openai.com/api-keys"],
            ["Click 'Create new secret key', name it CreatorOS, and copy it (it's shown only once)"],
            ["Make sure your account has credits (Billing)", "https://platform.openai.com/settings/organization/billing/overview"],
            ["Paste the key below, Save, then Test"],
            ["Under 'Use this AI', pick a model and click 'Use for writing' and/or 'Use for picking stories'"],
        ],
    },
    "telegram": {
        "label": "Telegram", "logo": "✈️", "color": "#4dc9ff", "group": "Approvals", "auth": "token",
        "fields": [{"name": "TELEGRAM_BOT_TOKEN", "label": "Bot token", "placeholder": "123456:ABC…"},
                   {"name": "TELEGRAM_CHAT_ID", "label": "Your chat ID", "placeholder": "click 'Find my chat ID'", "secret": False}],
        "steps": [
            ["Open @BotFather in Telegram", "https://t.me/BotFather"],
            ["Send /newbot, choose a name and a username ending in 'bot'"],
            ["Copy the token BotFather gives you, paste it below and click Save"],
            ["Open your new bot in Telegram and send it any message (e.g. hi)"],
            ["Click 'Find my chat ID' - it fills in automatically. Save, then restart CreatorOS"],
        ],
    },
    "linkedin": {
        "label": "LinkedIn", "logo": "in", "color": "#0a66c2", "group": "Publish", "auth": "oauth",
        "fields": [{"name": "LINKEDIN_CLIENT_ID", "label": "Client ID", "secret": False},
                   {"name": "LINKEDIN_CLIENT_SECRET", "label": "Client secret"}],
        "steps": [
            ["Open LinkedIn Developers and click 'Create app'", "https://www.linkedin.com/developers/apps/new"],
            ["Fill in a name (e.g. My CreatorOS) and link a LinkedIn Page (create a simple one if asked)"],
            ["In the 'Products' tab, request 'Sign In with LinkedIn using OpenID Connect' and 'Share on LinkedIn'"],
            ["In the 'Auth' tab, add the redirect URL shown below under 'Authorized redirect URLs'"],
            ["Copy the Client ID and Client secret from the 'Auth' tab, paste below, Save"],
            ["Click 'Connect LinkedIn' and allow access - done!"],
        ],
    },
    "youtube": {
        "label": "YouTube", "logo": "▶", "color": "#ff0000", "group": "Publish", "auth": "oauth",
        "fields": [{"name": "YOUTUBE_CLIENT_ID", "label": "Client ID", "secret": False},
                   {"name": "YOUTUBE_CLIENT_SECRET", "label": "Client secret"}],
        "steps": [
            ["Open Google Cloud and create a project (any name)", "https://console.cloud.google.com/projectcreate"],
            ["Enable the 'YouTube Data API v3' for that project", "https://console.cloud.google.com/apis/library/youtube.googleapis.com"],
            ["Set up the OAuth consent screen: choose 'External', fill the app name and your email, and add yourself under 'Test users'", "https://console.cloud.google.com/apis/credentials/consent"],
            ["Create credentials → 'OAuth client ID' → type 'Web application', and add the redirect URL shown below", "https://console.cloud.google.com/apis/credentials"],
            ["Copy the Client ID and Client secret, paste below, Save"],
            ["Click 'Connect YouTube', pick your channel and allow access - done!"],
        ],
    },
    "medium": {
        "label": "Medium", "logo": "M", "color": "#111111", "group": "Publish", "auth": "token",
        "fields": [{"name": "MEDIUM_TOKEN", "label": "Integration token"}],
        "steps": [
            ["Open Medium settings → 'Security and apps'", "https://medium.com/me/settings/security"],
            ["Under 'Integration tokens', create a token named CreatorOS and copy it (if you don't see this option, Medium no longer offers tokens to your account - use dev.to or the Markdown export instead)"],
            ["Paste it below, Save, then Test"],
        ],
    },
    "devto": {
        "label": "dev.to", "logo": "DEV", "color": "#3b49df", "group": "Publish", "auth": "token",
        "fields": [{"name": "DEVTO_API_KEY", "label": "API key"}],
        "steps": [
            ["Open dev.to → Settings → Extensions", "https://dev.to/settings/extensions"],
            ["Under 'DEV Community API Keys', generate a key named CreatorOS and copy it"],
            ["Paste it below, Save, then Test"],
        ],
    },
}

# Field names accepted from the dashboard (anything else is ignored).
ALLOWED_FIELDS = {f["name"] for p in PLATFORMS.values() for f in p["fields"]}


def _read() -> dict:
    if not STORE.exists():
        return {}
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write(data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    STORE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get(key: str) -> str | None:
    with _lock:
        value = _read().get("secrets", {}).get(key)
    return value or None


def set_many(values: dict) -> None:
    with _lock:
        data = _read()
        secrets = data.setdefault("secrets", {})
        for k, v in values.items():
            if v is None or str(v).strip() == "":
                secrets.pop(k, None)
            else:
                secrets[k] = str(v).strip()
        _write(data)


def get_oauth(platform: str) -> dict:
    with _lock:
        return dict(_read().get("oauth", {}).get(platform, {}))


def set_oauth(platform: str, info: dict | None) -> None:
    with _lock:
        data = _read()
        oauth = data.setdefault("oauth", {})
        if info is None:
            oauth.pop(platform, None)
        else:
            oauth[platform] = {**info, "saved_at": datetime.now().isoformat(timespec="seconds")}
        _write(data)


# ------------------------------------------------------- custom platforms
def list_custom() -> dict:
    with _lock:
        return dict(_read().get("custom", {}))


def save_custom(cid: str | None, spec: dict) -> str:
    import re

    name = (spec.get("name") or "").strip()
    url = (spec.get("url") or "").strip()
    if not name:
        raise ValueError("Give the platform a name")
    if not url.startswith(("https://", "http://")):
        raise ValueError("The webhook / API URL must start with https://")
    cid = cid or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] or "custom"
    with _lock:
        data = _read()
        custom = data.setdefault("custom", {})
        old = custom.get(cid, {})
        # Fields left empty or missing keep their saved value.
        custom[cid] = {
            "name": name[:40], "url": url,
            "method": (spec.get("method") or old.get("method") or "POST").upper(),
            "auth_header": (spec.get("auth_header") or old.get("auth_header") or "Authorization").strip(),
            "api_key": (spec.get("api_key") or "").strip() or old.get("api_key", ""),
            "send_media": bool(spec.get("send_media", old.get("send_media", True))),
            "color": spec.get("color") or old.get("color") or "#b49bff",
        }
        _write(data)
    return cid


def delete_custom(cid: str) -> None:
    with _lock:
        data = _read()
        data.get("custom", {}).pop(cid, None)
        _write(data)


def mask(value: str | None) -> str:
    if not value:
        return ""
    return value[:3] + "…" + value[-3:] if len(value) > 8 else "•••"
