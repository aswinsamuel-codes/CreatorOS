"""Folder → post: point the agent at a folder (certificates, project screenshots, event
photos...), give an instruction, and it inspects every file and writes social posts.

Modes:
  combined -> one post with all images (split into several posts above 20 images)
  series   -> one post per file, spaced out over time (e.g. one certificate a day)
"""

import base64
import io
import re
from datetime import datetime, timedelta
from pathlib import Path

from ... import db, notify
from ...config import WORKSPACE, log
from ...llm import LLMError, get_llm, parse_json
from ...profile import author_context

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED = IMAGE_EXT | {".pdf"}
MEDIA_DIR = WORKSPACE / "media"
MAX_IMAGES_PER_POST = 20          # LinkedIn multi-image limit
UPLOAD_MAX_PX = 2400              # stored copy used for publishing
VISION_MAX_PX = 1568              # copy sent to the model

PLATFORM_STYLE = {
    "linkedin": (
        "LinkedIn post. Plain text only (LinkedIn does not render Markdown: no **, no #headings, no "
        "bullet syntax other than simple dashes or emojis). Strong first line (it shows before 'see more'). "
        "Short paragraphs. Professional but warm and human, first person. 900-1800 characters. "
        "Credit the issuing organisations. Mention concrete skills. 3-6 relevant hashtags."
    ),
    "default": "Social media post. Plain text, short paragraphs, first person, 3-6 hashtags.",
}

ANALYZE_SYSTEM = (
    "You read images of documents such as certificates, badges, awards, diplomas, screenshots "
    "and event photos. Reply with JSON only. Never guess: use null for anything not visible."
)
ANALYZE_PROMPT = """Describe this file for a social media post. Return JSON:
{"type": "certificate|badge|award|diploma|screenshot|photo|other",
 "title": "<course / award / item name>", "issuer": "<organisation or null>",
 "date": "<date as shown or null>", "skills": ["<skill>", ...],
 "summary": "<one sentence>", "alt_text": "<accessible description, max 120 chars>"}
Do not copy personal ID numbers, certificate serial numbers, emails or phone numbers."""

COMPOSE_SYSTEM = """You write social media posts for the author described below, acting in the role given.

Rules:
- Follow the author's instruction first.
- Only state facts shown in the file details or the author's profile/documents. Never invent
  grades, dates, issuers or achievements.
- Never include certificate IDs, serial numbers, emails, phone numbers or addresses.
- Sound like a real person, not a press release. Avoid clichés like "thrilled to announce" unless asked.

AUTHOR PROFILE:
{profile}"""


# ----------------------------------------------------------------- files
def scan(folder: str | Path) -> list[Path]:
    folder = Path(folder).expanduser()
    if not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")
    files = [p for p in sorted(folder.iterdir()) if p.is_file() and p.suffix.lower() in SUPPORTED]
    if not files:
        raise FileNotFoundError(f"No images or PDFs in {folder} (supported: {', '.join(sorted(SUPPORTED))})")
    return files


def _to_pil(path: Path):
    from PIL import Image

    if path.suffix.lower() == ".pdf":
        import pymupdf

        with pymupdf.open(path) as doc:
            pix = doc[0].get_pixmap(dpi=170)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
    else:
        img = Image.open(path)
    img.load()
    if img.mode not in ("RGB", "L"):
        background = Image.new("RGB", img.size, "white")
        background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = background
    return img.convert("RGB")


def _resized_jpeg(img, max_px: int) -> bytes:
    img = img.copy()
    img.thumbnail((max_px, max_px))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def prepare(path: Path, out_dir: Path, index: int) -> dict:
    """Convert to a publishable JPEG + a smaller copy for the model."""
    img = _to_pil(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{index:02d}-{re.sub(r'[^A-Za-z0-9_-]+', '-', path.stem)[:40]}.jpg"
    out.write_bytes(_resized_jpeg(img, UPLOAD_MAX_PX))
    vision = base64.b64encode(_resized_jpeg(img, VISION_MAX_PX)).decode()
    return {"source": str(path), "path": str(out), "vision": ("image/jpeg", vision)}


# ------------------------------------------------------------- model work
def analyze(llm, item: dict) -> dict:
    try:
        info = parse_json(llm.complete(ANALYZE_SYSTEM, ANALYZE_PROMPT, max_tokens=4000, images=[item["vision"]]))
    except (LLMError, ValueError) as e:
        log.warning("Could not analyse %s: %s", item["source"], e)
        info = {}
    info.setdefault("title", Path(item["source"]).stem.replace("_", " ").replace("-", " "))
    info["alt_text"] = (info.get("alt_text") or info.get("summary") or info["title"])[:120]
    return info


def _details(items: list[dict]) -> str:
    lines = []
    for i, it in enumerate(items, 1):
        a = it["info"]
        parts = [f"{i}. {a.get('type') or 'file'}: {a.get('title')}"]
        if a.get("issuer"):
            parts.append(f"issuer: {a['issuer']}")
        if a.get("date"):
            parts.append(f"date: {a['date']}")
        if a.get("skills"):
            parts.append("skills: " + ", ".join(a["skills"]))
        if a.get("summary"):
            parts.append(f"note: {a['summary']}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def compose(llm, items: list[dict], instructions: str, platform: str, context: str) -> dict:
    style = PLATFORM_STYLE.get(platform, PLATFORM_STYLE["default"])
    prompt = f"""AUTHOR'S INSTRUCTION: {instructions or 'Share these with my network.'}

FORMAT: {style}
The post will include {len(items)} image(s) of these files, in this order:
{_details(items)}

Reply in exactly this format:
TITLE: <short internal title for my dashboard, max 70 characters>
HASHTAGS: <3-6 hashtags separated by spaces, e.g. #AI #CloudComputing>
===
<the post text, without the hashtags>"""
    text = llm.complete(COMPOSE_SYSTEM.format(profile=context), prompt, max_tokens=8000)
    head, sep, body = text.partition("\n===")
    if not sep:
        raise LLMError("Post reply was not in the expected format")
    meta = {}
    for line in head.strip().splitlines():
        k, _, v = line.partition(":")
        meta[k.strip().upper()] = v.strip()
    tags = [t if t.startswith("#") else f"#{t}" for t in meta.get("HASHTAGS", "").split() if t.strip("#")]
    body = body.lstrip("=").strip()
    return {"title": meta.get("TITLE") or "Folder post", "tags": [t.lstrip("#") for t in tags],
            "body": body + ("\n\n" + " ".join(tags) if tags else "")}


# ------------------------------------------------------------------- job
def create_posts(cfg: dict, folder: str, instructions: str, targets: list[str], mode: str = "combined",
                 interval_hours: float = 24, start_at: str | None = None, notify_user: bool = True,
                 role: str | None = None, custom_role: str | None = None) -> list[int]:
    files = scan(folder)
    context = author_context(cfg, role, custom_role)
    batch = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = MEDIA_DIR / batch
    vision_llm, writer = get_llm(cfg, "scout"), get_llm(cfg, "writer")
    platform = targets[0] if targets else "default"

    items = []
    for i, f in enumerate(files, 1):
        log.info("Inspecting %s (%d/%d)", f.name, i, len(files))
        item = prepare(f, out_dir, i)
        item["info"] = analyze(vision_llm, item)
        items.append(item)

    if mode == "series":
        groups = [[it] for it in items]
    else:
        groups = [items[i:i + MAX_IMAGES_PER_POST] for i in range(0, len(items), MAX_IMAGES_PER_POST)]

    start = datetime.fromisoformat(start_at) if start_at else datetime.now()
    approval = cfg.get("approval", {}).get("required", True)
    ids = []
    for n, group in enumerate(groups):
        extra = f" (part {n + 1} of {len(groups)})" if mode != "series" and len(groups) > 1 else ""
        post = compose(writer, group, instructions + extra, platform, context)
        when = start + timedelta(hours=interval_hours * n) if mode == "series" else start
        post_id = db.create_post(
            kind="social", angle="folder", topic=(instructions or "Folder post")[:200],
            title=post["title"], subtitle="", tags=post["tags"], body=post["body"],
            media=[{"path": it["path"], "alt": it["info"]["alt_text"]} for it in group],
            sources=[{"title": Path(it["source"]).name, "url": Path(it["source"]).as_uri()} for it in group],
            targets=targets, scheduled_at=when.isoformat(timespec="seconds"),
            status="pending" if approval else "scheduled", published={},
        )
        ids.append(post_id)
        log.info("Folder post #%d ready (%d images, publish at %s)", post_id, len(group), when)
        if approval and notify_user:
            notify.send_for_approval(db.get_post(post_id))
    if not approval:
        from ..blog import pipeline
        pipeline.publish_due(cfg)
    return ids


def revise(llm, post: dict, instructions: str, context: str) -> dict:
    prompt = f"""Revise this social media post according to the instruction. Keep facts accurate, keep it
plain text, keep the hashtags line at the end (adjust hashtags only if asked).

INSTRUCTION: {instructions}

CURRENT POST:
{post['body']}

Reply in exactly this format:
TITLE: <short internal title>
===
<the full revised post including hashtags>"""
    text = llm.complete(COMPOSE_SYSTEM.format(profile=context), prompt, max_tokens=8000)
    head, sep, body = text.partition("\n===")
    if not sep:
        raise LLMError("Revision was not in the expected format")
    title = head.strip().partition(":")[2].strip() or post["title"]
    body = body.lstrip("=").strip()
    return {"title": title, "body": body, "tags": [t.lstrip("#") for t in re.findall(r"#\w+", body)]}
