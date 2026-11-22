"""Notifications. Telegram is used when TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set;
otherwise posts simply wait in the dashboard."""

from ..config import log
from .telegram import Telegram

_bot: Telegram | None = None


def bot() -> Telegram | None:
    """The Telegram bot, or None. reset() makes it re-read the settings (after Connections change)."""
    global _bot
    if _bot is None:
        _bot = Telegram.from_env()
    return _bot


def reset() -> None:
    global _bot
    _bot = None


def send_for_approval(post: dict) -> None:
    b = bot()
    if b:
        try:
            b.send_for_approval(post)
        except Exception as e:
            log.error("Telegram approval message failed: %s", e)


def send_published(post: dict) -> None:
    b = bot()
    if b:
        try:
            b.send_published(post)
        except Exception as e:
            log.error("Telegram update failed: %s", e)


def send_text(text: str) -> None:
    b = bot()
    if b:
        try:
            b.send_text(text)
        except Exception as e:
            log.error("Telegram message failed: %s", e)
