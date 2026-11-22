"""Daily schedule: one post per slot, plus optional auto-publish of unanswered posts.

Slots come from blog.schedule in the config and can be changed live from the dashboard."""

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from . import db, notify
from .config import log
from .modules.blog import pipeline


def _run_slot(cfg: dict, angle: str) -> None:
    if cfg.get("paused"):
        log.info("Agent is paused - skipping '%s' slot", angle)
        return
    log.info("Scheduled slot: writing a '%s' post", angle)
    try:
        pipeline.generate_post(cfg, angle)
    except Exception as e:
        log.exception("Scheduled post failed")
        notify.send_text(f"⚠️ Scheduled '{angle}' post failed: {e}")


def _auto_publish(cfg: dict) -> None:
    minutes = cfg.get("approval", {}).get("auto_publish_after_minutes", 0)
    if not minutes or cfg.get("paused"):
        return
    cutoff = datetime.now() - timedelta(minutes=minutes)
    for post in db.list_posts(50, status="pending"):
        if datetime.fromisoformat(post["updated_at"]) < cutoff:
            log.info("Auto-publishing #%d (no answer for %d min)", post["id"], minutes)
            pipeline.publish_post(cfg, post["id"])


def _publish_due(cfg: dict) -> None:
    try:
        pipeline.publish_due(cfg)
    except Exception:
        log.exception("Publishing scheduled posts failed")


def _marketing(cfg: dict) -> None:
    try:
        from .modules.marketing import content
        content.generate_due(cfg)
    except Exception:
        log.exception("Marketing content generation failed")


def _add_slots(sched: BackgroundScheduler, cfg: dict) -> None:
    tz = cfg.get("timezone") or None
    for i, slot in enumerate(cfg["blog"].get("schedule", [])):
        if slot.get("enabled") is False:
            continue
        hour, minute = (int(x) for x in slot["time"].split(":"))
        days = slot.get("days", "*")  # e.g. "mon-fri" or "sat,sun"
        sched.add_job(_run_slot, "cron", hour=hour, minute=minute, day_of_week=days, timezone=tz,
                      args=[cfg, slot["angle"]], id=f"blog-{i}-{slot['time']}",
                      misfire_grace_time=1800, coalesce=True)


def start(cfg: dict) -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone=cfg.get("timezone") or None)
    _add_slots(sched, cfg)
    sched.add_job(_auto_publish, "interval", minutes=5, args=[cfg], id="auto-publish")
    sched.add_job(_publish_due, "interval", minutes=2, args=[cfg], id="publish-due")
    sched.add_job(_marketing, "interval", minutes=30, args=[cfg], id="marketing",
                  next_run_time=datetime.now() + timedelta(minutes=1))
    sched.start()
    for run in next_runs(sched):
        log.info("Scheduled %s (%s) -> next run %s", run["time"], run["angle"], run["next"])
    return sched


def reload(sched: BackgroundScheduler | None, cfg: dict) -> None:
    """Replace the slot jobs after settings changed."""
    if not sched:
        return
    for job in sched.get_jobs():
        if job.id.startswith("blog-"):
            job.remove()
    _add_slots(sched, cfg)
    log.info("Schedule reloaded: %d slots", len(next_runs(sched)))


def next_runs(sched: BackgroundScheduler | None) -> list[dict]:
    if not sched:
        return []
    runs = [{"time": j.id.split("-", 2)[2], "angle": j.args[1], "next": str(j.next_run_time)}
            for j in sched.get_jobs() if j.id.startswith("blog-")]
    return sorted(runs, key=lambda r: r["next"])
