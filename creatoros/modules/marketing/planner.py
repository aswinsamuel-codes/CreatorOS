"""Campaign planner: turns a goal into a strategy and a dated content calendar."""

import re
from datetime import date, datetime, timedelta

from ... import db
from ...config import log
from ...llm import LLMError, get_llm, parse_json
from ...profile import author_context
from .formats import DEFAULT_BEST_TIMES, FORMATS

SYSTEM = """You are a senior content-marketing strategist planning a campaign for the author below.
Plan realistically for one person: consistent, varied, and focused on the goal. Mix educational,
story/personal, proof (only real proof the author has) and promotional content (no more than 1 in 5
pieces should be promotional). Never invent statistics, clients or results.

{context}"""

PROMPT = """CAMPAIGN BRIEF
Name: {name}
Goal: {goal}
Audience: {audience}
Key message / offer: {message}
Links to promote: {links}
Extra notes: {notes}

PLAN
Dates: {start} to {end} ({weeks} week(s)), about {per_week} pieces per week in total.
Formats available (use only these ids): {formats}
Preferred posting times: {times}
Already published recently (avoid repeating): {recent}

Return JSON only:
{{"strategy": {{
    "positioning": "<one paragraph: how the author should be seen and why it matters to the audience>",
    "audience_insights": ["<pain point or desire>", "..."],
    "pillars": [{{"name": "<content pillar>", "description": "<what it covers>"}}],
    "kpis": ["<measurable target for this campaign>", "..."],
    "tips": ["<practical tip for running this campaign>", "..."]}},
  "calendar": [
    {{"date": "YYYY-MM-DD", "time": "HH:MM", "format": "<format id>", "pillar": "<pillar name>",
      "topic": "<specific topic>", "hook": "<the opening line or angle>", "cta": "<call to action>"}}]}}
Spread pieces evenly across days and formats. 3-5 pillars."""


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def clean_calendar(items: list, start: date, end: date, formats: list[str], best_times: dict) -> list[dict]:
    out, seen = [], set()
    for it in items or []:
        d = _parse_date(it.get("date", ""))
        fmt = it.get("format")
        if not d or not (start <= d <= end) or fmt not in formats or not it.get("topic"):
            continue
        t = str(it.get("time", ""))
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t):
            t = best_times.get(fmt, "10:00")
        key = (d, fmt, it["topic"].strip().lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({"due": f"{d.isoformat()}T{t}:00", "format": fmt, "pillar": (it.get("pillar") or "")[:80],
                    "topic": it["topic"].strip()[:300], "hook": (it.get("hook") or "").strip()[:300],
                    "cta": (it.get("cta") or "").strip()[:200]})
    return sorted(out, key=lambda x: x["due"])


def targets_for(fmt: str, brief: dict, cfg: dict) -> list[str]:
    chosen = (brief.get("targets") or {}).get(fmt)
    if chosen is not None:
        return list(chosen)
    default = FORMATS[fmt]["default_targets"]
    if default is None:  # blog: use the blog publish targets from settings
        return list(cfg.get("publish", {}).get("targets", ["markdown"]))
    return list(default)


def plan_campaign(cfg: dict, campaign_id: int) -> int:
    camp = db.get_campaign(campaign_id)
    brief = camp["brief"]
    formats = [f for f in brief.get("formats") or [] if f in FORMATS] or ["linkedin_post"]
    start = _parse_date(brief.get("start")) or date.today() + timedelta(days=1)
    weeks = max(1, min(int(brief.get("weeks") or 2), 12))
    end = start + timedelta(days=7 * weeks - 1)
    per_week = max(1, min(int(brief.get("per_week") or 5), 21))
    best_times = {**DEFAULT_BEST_TIMES, **(cfg.get("marketing", {}).get("best_times") or {})}
    try:
        context = author_context(cfg, brief.get("role") or "marketing_strategist", brief.get("custom_role"))
        prompt = PROMPT.format(
            name=camp["name"], goal=brief.get("goal", ""), audience=brief.get("audience", ""),
            message=brief.get("message", "") or "(none)", links=brief.get("links", "") or "(none)",
            notes=brief.get("notes", "") or "(none)", start=start, end=end, weeks=weeks, per_week=per_week,
            formats=", ".join(f"{f} ({FORMATS[f]['label']})" for f in formats),
            times=", ".join(f"{f} {best_times.get(f, '10:00')}" for f in formats),
            recent="; ".join(db.recent_titles(15)) or "(nothing yet)",
        )
        data = parse_json(get_llm(cfg, "writer").complete(SYSTEM.format(context=context), prompt, max_tokens=32000))
        items = clean_calendar(data.get("calendar"), start, end, formats, best_times)
        if not items:
            raise LLMError("The planner returned no usable calendar items")
    except Exception as e:
        log.exception("Campaign planning failed")
        db.update_campaign(campaign_id, status="failed", strategy={"error": str(e)})
        raise
    for it in items:
        db.add_calendar_item(campaign_id, **it, targets=targets_for(it["format"], brief, cfg))
    db.update_campaign(campaign_id, strategy=data.get("strategy") or {}, status="active")
    log.info("Campaign #%d planned: %d pieces from %s to %s", campaign_id, len(items), start, end)
    return len(items)
