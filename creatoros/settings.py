"""Validation for settings changed from the dashboard."""

import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .modules.blog.angles import all_angles
from .personas import PERSONAS
from .publishers import PUBLISHERS

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
EFFORTS = {None, "", "low", "medium", "high", "xhigh", "max"}


def validate(cfg: dict) -> list[str]:
    """Return a list of human-readable problems (empty = valid)."""
    errors = []
    blog = cfg.get("blog", {})
    angles = all_angles(cfg)

    tz = cfg.get("timezone")
    if tz:
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            errors.append(f"Unknown timezone '{tz}' (use names like Asia/Kolkata, Europe/London)")

    for i, slot in enumerate(blog.get("schedule", []), 1):
        if not TIME_RE.match(str(slot.get("time", ""))):
            errors.append(f"Slot {i}: time must be HH:MM (24h), got '{slot.get('time')}'")
        if slot.get("angle") not in angles:
            errors.append(f"Slot {i}: unknown post type '{slot.get('angle')}'")

    lo, hi = blog.get("words_min", 800), blog.get("words_max", 1500)
    if not (isinstance(lo, int) and isinstance(hi, int) and 100 <= lo < hi <= 6000):
        errors.append("Word count: min must be below max (100-6000)")

    for name, spec in (blog.get("angles") or {}).items():
        if not re.match(r"^[a-z0-9_]+$", name):
            errors.append(f"Post type name '{name}' must be lowercase letters, numbers or _")
        if not (spec or {}).get("write") and name not in all_angles():
            errors.append(f"Post type '{name}' needs 'write' instructions")

    for role in ("writer", "scout"):
        spec = cfg.get("models", {}).get(role, {})
        if spec.get("provider") not in cfg.get("providers", {}):
            errors.append(f"{role} model: unknown provider '{spec.get('provider')}'")
        if not spec.get("model"):
            errors.append(f"{role} model: model name is empty")
        if spec.get("effort") not in EFFORTS:
            errors.append(f"{role} model: effort must be low/medium/high/xhigh/max")

    for name, prov in cfg.get("providers", {}).items():
        if prov.get("type") not in ("anthropic", "openai_compatible"):
            errors.append(f"Provider '{name}': type must be anthropic or openai_compatible")
        if prov.get("type") == "openai_compatible" and not str(prov.get("base_url", "")).startswith("http"):
            errors.append(f"Provider '{name}': base_url must start with http")

    for t in cfg.get("publish", {}).get("targets", []):
        if t not in PUBLISHERS:
            errors.append(f"Unknown publish target '{t}'")
    status = cfg.get("publish", {}).get("medium", {}).get("publish_status", "draft")
    if status not in ("draft", "public", "unlisted"):
        errors.append("Medium status must be draft, public or unlisted")

    role = (cfg.get("persona") or {}).get("role", "tech_blogger")
    if role not in PERSONAS:
        errors.append(f"Unknown agent role '{role}'")
    elif role == "custom" and not (cfg.get("persona") or {}).get("custom", "").strip():
        errors.append("Custom agent role needs your instructions")
    if not isinstance(cfg.get("paused", False), bool):
        errors.append("paused must be true or false")
    mins = cfg.get("approval", {}).get("auto_publish_after_minutes", 0)
    if not isinstance(mins, int) or mins < 0:
        errors.append("Auto-publish minutes must be 0 or more")
    return errors
