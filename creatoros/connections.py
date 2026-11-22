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

# What the dashboard shows on the Connections tab.
PLATFORMS = {
    "linkedin": {
        "label": "LinkedIn", "auth": "oauth",
        "fields": ["LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET"],
        "help": "Create an app at developer.linkedin.com, add the products 'Sign In with LinkedIn using "
                "OpenID Connect' and 'Share on LinkedIn', and add the redirect URL shown here.",
    },
    "medium": {"label": "Medium", "auth": "token", "fields": ["MEDIUM_TOKEN"],
               "help": "Medium → Settings → Security and apps → Integration tokens."},
    "devto": {"label": "dev.to", "auth": "token", "fields": ["DEVTO_API_KEY"],
              "help": "dev.to → Settings → Extensions → DEV Community API Keys."},
    "telegram": {"label": "Telegram bot", "auth": "token", "fields": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
                 "help": "@BotFather → /newbot for the token; then run: python -m creatoros telegram-chat-id"},
    "claude": {"label": "Claude API", "auth": "token", "fields": ["ANTHROPIC_API_KEY"],
               "help": "console.anthropic.com → API keys."},
}


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


def mask(value: str | None) -> str:
    if not value:
        return ""
    return value[:3] + "…" + value[-3:] if len(value) > 8 else "•••"
