"""Tiny SQLite store for posts and already-used stories."""

import json
import sqlite3
import threading
from datetime import datetime

from .config import DATA_DIR

DB_PATH = DATA_DIR / "creatoros.db"
_lock = threading.Lock()
JSON_FIELDS = ("sources", "tags", "published", "media", "targets", "meta")
DICT_FIELDS = ("published", "meta")

# Columns added after v0.1 (added automatically to older databases).
MIGRATIONS = {
    "kind": "TEXT DEFAULT 'blog'",   # blog | social
    "media": "TEXT",                 # [{"path": "...", "alt": "..."}]
    "targets": "TEXT",               # per-post publish targets, e.g. ["linkedin"]
    "scheduled_at": "TEXT",          # publish at/after this time (ISO)
    "meta": "TEXT",                  # platform-specific extras, e.g. {"linkedin_text": "...", "youtube": {...}}
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT, updated_at TEXT,
    angle TEXT, topic TEXT, sources TEXT,
    title TEXT, subtitle TEXT, tags TEXT, body TEXT,
    status TEXT,           -- pending | approved | published | rejected | failed
    published TEXT,        -- {"medium": "https://..."}
    error TEXT
);
CREATE TABLE IF NOT EXISTS seen (
    key TEXT PRIMARY KEY, title TEXT, used_at TEXT
);
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT, name TEXT, brief TEXT, strategy TEXT,
    status TEXT            -- planning | active | paused | failed
);
CREATE TABLE IF NOT EXISTS calendar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER, due TEXT, format TEXT, pillar TEXT, topic TEXT, hook TEXT, cta TEXT,
    targets TEXT, post_id INTEGER,
    status TEXT            -- planned | writing | drafted | skipped | failed
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with _lock, _connect() as c:
        c.executescript(SCHEMA)
        existing = {r["name"] for r in c.execute("PRAGMA table_info(posts)").fetchall()}
        for col, decl in MIGRATIONS.items():
            if col not in existing:
                c.execute(f"ALTER TABLE posts ADD COLUMN {col} {decl}")


def due_scheduled(now_iso: str) -> list[dict]:
    with _lock, _connect() as c:
        rows = c.execute(
            "SELECT * FROM posts WHERE status = 'scheduled' AND (scheduled_at IS NULL OR scheduled_at <= ?)",
            (now_iso,),
        ).fetchall()
    return [_decode(r) for r in rows]


def _decode(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for k in JSON_FIELDS:
        d[k] = json.loads(d[k]) if d.get(k) else ({} if k in DICT_FIELDS else [])
    d["kind"] = d.get("kind") or "blog"
    return d


def _encode(fields: dict) -> dict:
    out = dict(fields)
    for k in JSON_FIELDS:
        if k in out and not isinstance(out[k], str):
            out[k] = json.dumps(out[k], ensure_ascii=False)
    return out


def create_post(**fields) -> int:
    fields = _encode({**fields, "created_at": _now(), "updated_at": _now()})
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    with _lock, _connect() as c:
        cur = c.execute(f"INSERT INTO posts ({cols}) VALUES ({marks})", list(fields.values()))
        return cur.lastrowid


def update_post(post_id: int, **fields) -> None:
    fields = _encode({**fields, "updated_at": _now()})
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _lock, _connect() as c:
        c.execute(f"UPDATE posts SET {sets} WHERE id = ?", [*fields.values(), post_id])


def get_post(post_id: int) -> dict | None:
    with _lock, _connect() as c:
        return _decode(c.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone())


def list_posts(limit: int = 50, status: str | None = None) -> list[dict]:
    q, args = "SELECT * FROM posts", []
    if status:
        q, args = q + " WHERE status = ?", [status]
    q += " ORDER BY id DESC LIMIT ?"
    with _lock, _connect() as c:
        return [_decode(r) for r in c.execute(q, [*args, limit]).fetchall()]


# ------------------------------------------------------------- campaigns
def _row(r: sqlite3.Row | None, json_keys: tuple) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    for k in json_keys:
        d[k] = json.loads(d[k]) if d.get(k) else ([] if k == "targets" else {})
    return d


def create_campaign(name: str, brief: dict) -> int:
    with _lock, _connect() as c:
        return c.execute("INSERT INTO campaigns (created_at, name, brief, strategy, status) VALUES (?, ?, ?, ?, ?)",
                         (_now(), name, json.dumps(brief, ensure_ascii=False), "{}", "planning")).lastrowid


def update_campaign(cid: int, **fields) -> None:
    for k in ("brief", "strategy"):
        if k in fields and not isinstance(fields[k], str):
            fields[k] = json.dumps(fields[k], ensure_ascii=False)
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _lock, _connect() as c:
        c.execute(f"UPDATE campaigns SET {sets} WHERE id = ?", [*fields.values(), cid])


def get_campaign(cid: int) -> dict | None:
    with _lock, _connect() as c:
        return _row(c.execute("SELECT * FROM campaigns WHERE id = ?", (cid,)).fetchone(), ("brief", "strategy"))


def list_campaigns() -> list[dict]:
    with _lock, _connect() as c:
        return [_row(r, ("brief", "strategy")) for r in c.execute("SELECT * FROM campaigns ORDER BY id DESC")]


def delete_campaign(cid: int) -> None:
    with _lock, _connect() as c:
        c.execute("DELETE FROM calendar WHERE campaign_id = ?", (cid,))
        c.execute("DELETE FROM campaigns WHERE id = ?", (cid,))


def add_calendar_item(campaign_id: int, **item) -> int:
    item = {**item, "campaign_id": campaign_id, "status": item.get("status", "planned"),
            "targets": json.dumps(item.get("targets") or [])}
    cols = ", ".join(item)
    with _lock, _connect() as c:
        return c.execute(f"INSERT INTO calendar ({cols}) VALUES ({', '.join('?' for _ in item)})",
                         list(item.values())).lastrowid


def update_calendar_item(item_id: int, **fields) -> None:
    if "targets" in fields and not isinstance(fields["targets"], str):
        fields["targets"] = json.dumps(fields["targets"])
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _lock, _connect() as c:
        c.execute(f"UPDATE calendar SET {sets} WHERE id = ?", [*fields.values(), item_id])


def get_calendar_item(item_id: int) -> dict | None:
    with _lock, _connect() as c:
        return _row(c.execute("SELECT * FROM calendar WHERE id = ?", (item_id,)).fetchone(), ("targets",))


def list_calendar(campaign_id: int) -> list[dict]:
    with _lock, _connect() as c:
        rows = c.execute("SELECT * FROM calendar WHERE campaign_id = ? ORDER BY due", (campaign_id,)).fetchall()
    return [_row(r, ("targets",)) for r in rows]


def calendar_due(before_iso: str) -> list[dict]:
    """Planned items of active campaigns that are due before the given time."""
    with _lock, _connect() as c:
        rows = c.execute(
            "SELECT calendar.* FROM calendar JOIN campaigns ON campaigns.id = calendar.campaign_id "
            "WHERE calendar.status = 'planned' AND campaigns.status = 'active' AND calendar.due <= ? "
            "ORDER BY calendar.due", (before_iso,)).fetchall()
    return [_row(r, ("targets",)) for r in rows]


def recent_titles(n: int = 30) -> list[str]:
    with _lock, _connect() as c:
        rows = c.execute(
            "SELECT title FROM posts WHERE status != 'rejected' ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
    return [r["title"] for r in rows if r["title"]]


def mark_seen(key: str, title: str = "") -> None:
    with _lock, _connect() as c:
        c.execute("INSERT OR IGNORE INTO seen (key, title, used_at) VALUES (?, ?, ?)", (key, title, _now()))


def seen_keys() -> set[str]:
    with _lock, _connect() as c:
        return {r["key"] for r in c.execute("SELECT key FROM seen").fetchall()}
