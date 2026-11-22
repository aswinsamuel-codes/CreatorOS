"""Writes campaign content (and repurposes existing posts) in any format."""

from datetime import datetime, timedelta

from ... import db, notify
from ...config import log
from ...llm import LLMError, get_llm, parse_json
from ...profile import author_context
from .formats import FORMATS
from .planner import targets_for

SYSTEM = """You create marketing content for the author below, acting in the role given.

Rules:
- Serve the campaign goal and audience. One clear call to action.
- Never invent statistics, testimonials, clients, results or quotes. Use only facts from the brief,
  the author's profile/documents, or well-known general knowledge.
- Write natively for the format (as a skilled creator on that platform would).
- Never include private contact details unless they are in the brief's links.

{context}"""

ITEM_PROMPT = """CAMPAIGN: {name}
Goal: {goal}
Audience: {audience}
Key message / offer: {message}
Links: {links}

THIS PIECE
Content pillar: {pillar}
Topic: {topic}
Hook idea: {hook}
Call to action: {cta}

FORMAT: {spec}

Return JSON only: {{"title": "<headline or internal title>", "subtitle": "<one-line summary>",
"body": "<the complete content, ready to use>", "hashtags": ["#..."]}}
If the format already puts hashtags inside the body, still list them in "hashtags"."""

REPURPOSE_PROMPT = """Repurpose the source content below into a new format. Keep the core ideas and facts; adapt the
structure, length and tone to the new format so it feels native, not copy-pasted.
{extra}
SOURCE TITLE: {title}
SOURCE CONTENT:
{body}

NEW FORMAT: {spec}

Return JSON only: {{"title": "...", "subtitle": "...", "body": "<complete content>", "hashtags": ["#..."]}}"""


def _parse(text: str, fmt: str) -> dict:
    data = parse_json(text)
    body = (data.get("body") or "").strip()
    if not body:
        raise LLMError("The writer returned an empty piece")
    tags = [h if h.startswith("#") else f"#{h}" for h in data.get("hashtags") or [] if str(h).strip("#")]
    if FORMATS[fmt]["kind"] == "social" and tags and not any(t.lower() in body.lower() for t in tags):
        body += "\n\n" + " ".join(tags[:5])
    return {"title": (data.get("title") or "Untitled")[:150], "subtitle": (data.get("subtitle") or "")[:250],
            "body": body, "tags": [t.lstrip("#") for t in tags][:10]}


def _save_post(cfg: dict, fmt: str, piece: dict, targets: list[str], when: str | None, topic: str,
               meta: dict) -> int:
    kind = FORMATS[fmt]["kind"]
    if not targets:  # nowhere to publish (e.g. an X thread without a connected platform) → draft for you
        kind = "draft"
    approval = cfg.get("approval", {}).get("required", True)
    if kind == "draft":
        status = "pending" if approval else "ready"
        targets = []
    else:
        status = "pending" if approval else "scheduled"
    post_id = db.create_post(
        kind=kind, angle=fmt, topic=topic[:200], title=piece["title"], subtitle=piece["subtitle"],
        tags=piece["tags"], body=piece["body"], targets=targets, scheduled_at=when, published={},
        media=[], sources=[], meta={**meta, "format": fmt, "format_label": FORMATS[fmt]["label"]},
        status=status,
    )
    if status == "pending":
        notify.send_for_approval(db.get_post(post_id))
    return post_id


def write_item(cfg: dict, item_id: int) -> int:
    item = db.get_calendar_item(item_id)
    camp = db.get_campaign(item["campaign_id"])
    brief = camp["brief"]
    db.update_calendar_item(item_id, status="writing")
    try:
        context = author_context(cfg, brief.get("role") or "marketing_strategist", brief.get("custom_role"))
        prompt = ITEM_PROMPT.format(
            name=camp["name"], goal=brief.get("goal", ""), audience=brief.get("audience", ""),
            message=brief.get("message") or "(none)", links=brief.get("links") or "(none)",
            pillar=item["pillar"] or "-", topic=item["topic"], hook=item["hook"] or "-", cta=item["cta"] or "-",
            spec=FORMATS[item["format"]]["spec"],
        )
        piece = _parse(get_llm(cfg, "writer").complete(SYSTEM.format(context=context), prompt, max_tokens=16000),
                       item["format"])
        post_id = _save_post(cfg, item["format"], piece, item["targets"], item["due"], item["topic"],
                             {"campaign_id": camp["id"], "campaign": camp["name"], "calendar_id": item_id})
    except Exception:
        db.update_calendar_item(item_id, status="failed")
        log.exception("Writing calendar item #%d failed", item_id)
        raise
    db.update_calendar_item(item_id, status="drafted", post_id=post_id)
    log.info("Calendar item #%d written as post #%d", item_id, post_id)
    return post_id


def generate_due(cfg: dict, hours: float | None = None) -> list[int]:
    """Write every planned item due within the lead time (default marketing.lead_hours)."""
    if cfg.get("paused"):
        return []
    lead = hours if hours is not None else float(cfg.get("marketing", {}).get("lead_hours", 24))
    horizon = (datetime.now() + timedelta(hours=lead)).isoformat(timespec="seconds")
    ids = []
    for item in db.calendar_due(horizon):
        try:
            ids.append(write_item(cfg, item["id"]))
        except Exception as e:
            notify.send_text(f"⚠️ Could not write '{item['topic'][:60]}': {e}")
    return ids


def repurpose(cfg: dict, post_id: int, formats: list[str], targets: dict | None = None,
              instructions: str = "") -> list[int]:
    src = db.get_post(post_id)
    if not src:
        raise ValueError(f"Post #{post_id} not found")
    text = (src.get("meta") or {}).get("linkedin_text") if src.get("kind") == "video" else ""
    body = f"{src['body']}\n\n{text}".strip()
    context = author_context(cfg)
    writer = get_llm(cfg, "writer")
    ids = []
    for fmt in formats:
        if fmt not in FORMATS:
            continue
        prompt = REPURPOSE_PROMPT.format(title=src["title"], body=body[:20000], spec=FORMATS[fmt]["spec"],
                                         extra=f"Author's note: {instructions}\n" if instructions else "")
        piece = _parse(writer.complete(SYSTEM.format(context=context), prompt, max_tokens=16000), fmt)
        tg = (targets or {}).get(fmt)
        tg = list(tg) if tg is not None else targets_for(fmt, {}, cfg)
        ids.append(_save_post(cfg, fmt, piece, tg, None, f"Repurposed from #{post_id}: {src['title']}",
                              {"repurposed_from": post_id}))
    return ids
