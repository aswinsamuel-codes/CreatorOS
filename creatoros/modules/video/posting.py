"""Video → post: inspect videos and write platform metadata, then publish after approval.

For each video: probe (duration, orientation), sample frames, optional transcript →
the writer model (vision) produces a YouTube title, description, tags, chapters and a
LinkedIn caption → one post per video, scheduled one after another.
"""

import re
from datetime import datetime, timedelta
from pathlib import Path

from ... import db, notify
from ...config import WORKSPACE, log
from ...llm import LLMError, get_llm, parse_json
from ...profile import author_context
from . import videoinfo

MEDIA_DIR = WORKSPACE / "media"
SHORTS_MAX_SECONDS = 180

SYSTEM = """You are a video marketing specialist who writes YouTube and LinkedIn metadata for this author,
acting in the role given below.

Rules:
- Follow the author's instruction first.
- Describe only what the frames and transcript show. Never invent features, results or claims.
- YouTube title: max 90 characters, specific and curiosity-driven, no clickbait, no ALL CAPS, no < or >.
- YouTube description: first 2 lines are the hook (they show in search). Then what viewers will learn or see,
  then relevant links mentioned by the author, then a call to action. Plain text, max 3000 characters, no < or >.
- Tags: 8-15 search phrases people actually type.
- LinkedIn caption: plain text, strong first line, short paragraphs, 500-1300 characters, first person.
- Never include emails, phone numbers or private details.

{context}"""

PROMPT = """AUTHOR'S INSTRUCTION: {instructions}

VIDEO FACTS: file "{name}", duration {duration}, {orientation}{short_note}.
The images are {frames} frames sampled evenly through the video (frame 0 is near the start).

TRANSCRIPT (with timestamps):
{transcript}

Return JSON only:
{{"title": "...", "description": "...", "tags": ["..."],
  "chapters": [{{"time": "0:00", "title": "..."}}],
  "hashtags": ["#...", "#..."], "linkedin_text": "...",
  "thumbnail_frame": <index of the frame that would make the best thumbnail>}}
Only include chapters if the transcript supports them (first must be 0:00, at least 3, at least 10 seconds apart);
otherwise return an empty list."""


def _clean(text: str) -> str:
    return re.sub(r"[<>]", "", text or "").strip()


def _valid_chapters(chapters: list, duration: float) -> list[dict]:
    def secs(t: str) -> int:
        parts = [int(x) for x in str(t).split(":") if x.strip().isdigit()]
        total = 0
        for p in parts:
            total = total * 60 + p
        return total

    out, last = [], -10
    for ch in chapters or []:
        s = secs(ch.get("time", ""))
        if s - last < 10 or (duration and s >= duration) or not ch.get("title"):
            continue
        out.append({"time": videoinfo.fmt_time(s), "title": _clean(ch["title"])[:80], "s": s})
        last = s
    if len(out) < 3 or out[0]["s"] != 0:
        return []
    return [{"time": c["time"], "title": c["title"]} for c in out]


def build_description(meta: dict, chapters: list[dict], hashtags: list[str], short: bool) -> str:
    desc = _clean(meta.get("description", ""))
    if chapters:
        desc += "\n\nChapters:\n" + "\n".join(f"{c['time']} {c['title']}" for c in chapters)
    tags_line = " ".join(dict.fromkeys((["#Shorts"] if short else []) + hashtags))
    if tags_line:
        desc += "\n\n" + tags_line
    return desc[:4900]


def _fit_tags(tags: list[str]) -> list[str]:
    out, total = [], 0
    for t in tags:
        t = _clean(t).replace(",", "")[:60]
        if t and total + len(t) + 2 <= 480:
            out.append(t)
            total += len(t) + 2
    return out


def write_metadata(llm, video: Path, info: dict, frames: list[Path], transcript: str, instructions: str,
                   context: str) -> dict:
    short = info["vertical"] and info["duration"] <= SHORTS_MAX_SECONDS
    prompt = PROMPT.format(
        instructions=instructions or "Publish this video for my audience.",
        name=video.name, duration=videoinfo.fmt_time(info["duration"]),
        orientation="vertical" if info["vertical"] else "horizontal",
        short_note=" (will be published as a YouTube Short)" if short else "",
        frames=len(frames), transcript=transcript or "(no transcript available - rely on the frames)",
    )
    data = parse_json(llm.complete(SYSTEM.format(context=context), prompt, max_tokens=12000,
                                   images=[videoinfo.frame_b64(f) for f in frames]))
    title = _clean(data.get("title") or video.stem)[:95]
    if short and "#shorts" not in title.lower() and len(title) <= 88:
        title += " #Shorts"
    hashtags = [h if h.startswith("#") else f"#{h}" for h in (data.get("hashtags") or []) if h.strip("#")][:6]
    chapters = _valid_chapters(data.get("chapters"), info["duration"])
    idx = data.get("thumbnail_frame")
    thumb = frames[idx] if isinstance(idx, int) and 0 <= idx < len(frames) else frames[len(frames) // 2]
    linkedin = _clean(data.get("linkedin_text", ""))
    if hashtags and linkedin:
        linkedin += "\n\n" + " ".join(hashtags)
    return {
        "title": title, "description": build_description(data, chapters, hashtags, short),
        "tags": _fit_tags(data.get("tags") or []), "chapters": chapters, "linkedin_text": linkedin,
        "thumb": str(thumb), "short": short,
    }


def create_posts(cfg: dict, path: str, instructions: str, targets: list[str], privacy: str = "private",
                 category_id: str = "28", interval_hours: float = 24, start_at: str | None = None,
                 transcribe: bool = True, notify_user: bool = True, role: str | None = None,
                 custom_role: str | None = None) -> list[int]:
    videos = videoinfo.scan(path)
    context = author_context(cfg, role, custom_role)
    writer = get_llm(cfg, "writer")
    start = datetime.fromisoformat(start_at) if start_at else datetime.now()
    approval = cfg.get("approval", {}).get("required", True)
    batch = datetime.now().strftime("%Y%m%d-%H%M%S")
    ids = []
    for n, video in enumerate(videos):
        log.info("Inspecting video %s (%d/%d)", video.name, n + 1, len(videos))
        info = videoinfo.probe(video)
        frames = videoinfo.extract_frames(video, info["duration"], MEDIA_DIR / batch / f"{n:02d}")
        segments = videoinfo.transcribe(video) if transcribe and info["has_audio"] else None
        meta = write_metadata(writer, video, info, frames, videoinfo.transcript_text(segments), instructions, context)
        when = start + timedelta(hours=interval_hours * n)
        post_id = db.create_post(
            kind="video", angle="video", topic=(instructions or video.name)[:200],
            title=meta["title"], subtitle="", tags=meta["tags"], body=meta["description"],
            media=[{"path": str(video), "type": "video", "thumb": meta["thumb"], "alt": meta["title"]}],
            sources=[{"title": video.name, "url": video.as_uri()}],
            meta={"linkedin_text": meta["linkedin_text"], "chapters": meta["chapters"],
                  "youtube": {"privacy": privacy, "category_id": str(category_id), "short": meta["short"]},
                  "duration": info["duration"], "vertical": info["vertical"],
                  "transcript": bool(segments)},
            targets=targets, scheduled_at=when.isoformat(timespec="seconds"),
            status="pending" if approval else "scheduled", published={},
        )
        ids.append(post_id)
        log.info("Video post #%d ready: %s", post_id, meta["title"])
        if approval and notify_user:
            notify.send_for_approval(db.get_post(post_id))
    if not approval:
        from ..blog import pipeline
        pipeline.publish_due(cfg)
    return ids


def revise(llm, post: dict, instructions: str, context: str) -> dict:
    meta = post.get("meta") or {}
    prompt = f"""Revise this video's metadata according to the instruction. Keep facts accurate.

INSTRUCTION: {instructions}

CURRENT:
TITLE: {post['title']}
TAGS: {', '.join(post.get('tags') or [])}
YOUTUBE DESCRIPTION:
{post['body']}

LINKEDIN CAPTION:
{meta.get('linkedin_text', '')}

Return JSON only: {{"title": "...", "description": "<full YouTube description>", "tags": ["..."],
"linkedin_text": "<full LinkedIn caption including hashtags>"}}"""
    data = parse_json(llm.complete(SYSTEM.format(context=context), prompt, max_tokens=12000))
    if not data.get("title"):
        raise LLMError("Revision was missing a title")
    return {
        "title": _clean(data["title"])[:100], "body": _clean(data.get("description") or post["body"])[:4900],
        "tags": _fit_tags(data.get("tags") or post.get("tags") or []),
        "meta": {**meta, "linkedin_text": _clean(data.get("linkedin_text") or meta.get("linkedin_text", ""))},
    }
