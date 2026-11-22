"""Your personal details and own content, used to personalise every post."""

import yaml

from . import db
from .config import PROFILE_DIR

PROFILE_FILE = PROFILE_DIR / "profile.yaml"            # yours, ignored by git
PROFILE_EXAMPLE = PROFILE_DIR / "profile.example.yaml"  # template, in git
NOTES_DIR = PROFILE_DIR / "notes"


def ensure_profile() -> None:
    """Create profile.yaml from the template on first run."""
    if not PROFILE_FILE.exists() and PROFILE_EXAMPLE.exists():
        PROFILE_FILE.write_text(PROFILE_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")


def load_profile() -> dict:
    ensure_profile()
    if not PROFILE_FILE.exists():
        return {}
    with open(PROFILE_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def author_context(cfg: dict, role: str | None = None, custom: str | None = None) -> str:
    """Agent role + author profile + documents: the background every writer prompt gets."""
    from .personas import persona_prompt

    return persona_prompt(cfg, role, custom) + "\n\n" + profile_prompt()


def profile_prompt() -> str:
    """Profile fields plus the author's enabled documents (resume etc.)."""
    from .documents import documents_prompt

    text = _profile_fields()
    docs = documents_prompt()
    if docs:
        text += (
            "\n\nAUTHOR DOCUMENTS (background about the author, e.g. resume, projects). Use them to add "
            "genuine, relevant experience and credibility where it fits naturally - don't force it into "
            "every post. Never include private details from them: no phone numbers, emails, home "
            "addresses, ID numbers, salaries or names of private individuals.\n\n" + docs
        )
    return text


def _profile_fields() -> str:
    p = load_profile()
    if not p:
        return "(no profile set)"
    lines = []
    for key, value in p.items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        elif isinstance(value, dict):
            value = "; ".join(f"{k}: {v}" for k, v in value.items() if v)
        lines.append(f"- {key.replace('_', ' ')}: {str(value).strip()}")
    return "\n".join(lines)


def list_notes() -> list[dict]:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    notes = []
    for f in sorted(NOTES_DIR.glob("*.md")) + sorted(NOTES_DIR.glob("*.txt")):
        if f.name.lower() == "readme.md":
            continue
        notes.append({"name": f.name, "content": f.read_text(encoding="utf-8")})
    return notes


def next_unused_note() -> dict | None:
    used = db.seen_keys()
    for note in list_notes():
        if f"note:{note['name']}" not in used and note["content"].strip():
            return note
    return None
