"""The full blog flow: scout -> pick -> research -> write -> save -> ask for approval -> publish."""

import re
from datetime import datetime

from ... import db, notify
from ...config import BLOG_OUTPUT, log
from ...llm import LLMError, get_llm
from ...profile import author_context, next_unused_note
from ...publishers import publish_to
from . import research, scout, writer

REVIEW_INSTRUCTIONS = (
    "Act as a strict editor: tighten weak sentences, fix unclear explanations, make the hook and title "
    "stronger, remove any claim the sources don't support, and keep the length within the target."
)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "post"


def save_markdown(post: dict) -> str:
    BLOG_OUTPUT.mkdir(parents=True, exist_ok=True)
    path = BLOG_OUTPUT / f"{post['id']:04d}-{_slug(post['title'])}.md"
    tags = ", ".join(post.get("tags", []))
    path.write_text(
        f"# {post['title']}\n\n*{post.get('subtitle', '')}*\n\nTags: {tags}\n\n{post['body']}\n",
        encoding="utf-8",
    )
    return str(path)


def generate_post(cfg: dict, angle: str = "news", topic_hint: str | None = None, notify_user: bool = True) -> int:
    note = None
    if angle == "personal":
        note = next_unused_note()
        if not note:
            log.info("No unused notes in profile/notes - switching personal slot to 'future'")
            angle = "future"

    writer_llm = get_llm(cfg, "writer")
    profile_text = author_context(cfg)

    if note:
        topic, sources, used_keys = f"The author's note '{note['name']}'", [], [f"note:{note['name']}"]
    else:
        candidates = scout.gather(cfg)
        if not candidates:
            raise LLMError("Scout found no fresh stories (check your internet connection)")
        pick = writer.pick_story(get_llm(cfg, "scout"), angle, candidates, cfg, db.recent_titles(), topic_hint)
        topic = pick["topic"]
        chosen = [pick["main"], *pick["related"]]
        log.info("Picked story: %s", pick["main"]["title"])
        sources = [{"title": c["title"], "url": c["url"], "text": research.fetch_text(c["url"])} for c in chosen]
        used_keys = [c["key"] for c in chosen]

    post = writer.write_post(writer_llm, angle, topic, sources, profile_text, cfg, note=note)
    if cfg["blog"].get("review_pass"):
        post = writer.revise_post(writer_llm, post, REVIEW_INSTRUCTIONS, profile_text)

    status = "pending" if cfg.get("approval", {}).get("required", True) else "approved"
    post_id = db.create_post(
        angle=angle, topic=topic, status=status, published={},
        sources=[{"title": s["title"], "url": s["url"]} for s in sources],
        **post,
    )
    for k in used_keys:
        db.mark_seen(k, post["title"])
    saved = db.get_post(post_id)
    log.info("Post #%d written: %s -> %s", post_id, post["title"], save_markdown(saved))

    if status == "approved":
        publish_post(cfg, post_id)
    elif notify_user:
        notify.send_for_approval(saved)
    return post_id


def approve(cfg: dict, post_id: int) -> str:
    """Approve a post: publish now, or keep it until its scheduled time (series posts)."""
    post = db.get_post(post_id)
    if not post:
        raise ValueError(f"Post #{post_id} not found")
    when = post.get("scheduled_at")
    if when and datetime.fromisoformat(when) > datetime.now():
        db.update_post(post_id, status="scheduled")
        notify.send_text(f"🗓️ #{post_id} approved, it will be published at {when.replace('T', ' ')}.")
        return "scheduled"
    publish_post(cfg, post_id)
    return db.get_post(post_id)["status"]


def publish_due(cfg: dict) -> None:
    """Publish approved posts whose scheduled time has come (runs every few minutes)."""
    if cfg.get("paused"):
        return
    for post in db.due_scheduled(datetime.now().isoformat(timespec="seconds")):
        log.info("Scheduled post #%d is due", post["id"])
        publish_post(cfg, post["id"])


def publish_post(cfg: dict, post_id: int) -> dict:
    post = db.get_post(post_id)
    if not post:
        raise ValueError(f"Post #{post_id} not found")
    results, errors = dict(post.get("published") or {}), []
    targets = post.get("targets") or cfg.get("publish", {}).get("targets", ["markdown"])
    for target in targets:
        if target in results:
            continue  # already published there
        try:
            results[target] = publish_to(target, post, cfg)
            log.info("Post #%d published to %s: %s", post_id, target, results[target])
        except Exception as e:
            log.error("Publishing #%d to %s failed: %s", post_id, target, e)
            errors.append(f"{target}: {e}")
    status = "failed" if errors and not results else "published"
    db.update_post(post_id, status=status, published=results, error="; ".join(errors) or None)
    notify.send_published(db.get_post(post_id))
    return results


def revise(cfg: dict, post_id: int, instructions: str) -> None:
    post = db.get_post(post_id)
    if post.get("kind") == "social":
        from ..social import folder
        new = folder.revise(get_llm(cfg, "writer"), post, instructions, author_context(cfg))
    else:
        new = writer.revise_post(get_llm(cfg, "writer"), post, instructions, author_context(cfg))
    db.update_post(post_id, **new, status="pending")
    updated = db.get_post(post_id)
    save_markdown(updated)
    notify.send_for_approval(updated)


def reject(post_id: int) -> None:
    db.update_post(post_id, status="rejected")
