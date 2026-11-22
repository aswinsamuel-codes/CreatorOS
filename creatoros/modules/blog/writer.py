"""Pick a story and write the post."""

from datetime import date

from ...llm import LLMError, parse_json
from .angles import get_angle

EDITOR_SYSTEM = (
    "You are the editor of a popular tech blog read by technical people from many fields. "
    "You choose stories that are surprising, important or exciting, and never repeat a story already covered. "
    "Reply with JSON only."
)

WRITER_SYSTEM = """You are the lead writer for this author's tech blog on Medium.

Rules:
- Write original, engaging posts. Never copy sentences from the sources; synthesise and add insight.
- Never invent facts, numbers, quotes, names or dates. Use only what the sources support or what is
  well established. If something is uncertain, say so or leave it out.
- Match the tone to the topic: playful and casual for fun or quirky stories; clear and authoritative
  for serious ones.
- Write in the author's voice, as described in their profile. Never claim experiences the author
  didn't describe.

AUTHOR PROFILE:
{profile}"""


def pick_story(llm, angle_name: str, candidates: list[dict], cfg: dict, recent: list[str],
               topic_hint: str | None = None) -> dict:
    angle = get_angle(angle_name, cfg)
    blog = cfg["blog"]
    listing = "\n".join(
        f"{i}. [{c['source']}{', ' + str(c['score']) + ' pts' if c['score'] else ''}] {c['title']}"
        for i, c in enumerate(candidates[:120])
    )
    hint = f"\nThe author specifically wants a post about: {topic_hint}\nPrefer candidates about that.\n" if topic_hint else ""
    prompt = f"""Post type: {angle['label']}. {angle['pick']}
Preferred topics: {', '.join(blog.get('topics', []))}
Avoid: {', '.join(blog.get('avoid', []))}
Already covered recently (do not repeat these stories):
{chr(10).join('- ' + t for t in recent) or '- (nothing yet)'}
{hint}
Candidates:
{listing}

Return JSON: {{"index": <number of the best candidate>, "related": [<other candidate numbers covering the same story>], "topic": "<one line: the angle this post should take>"}}"""
    data = parse_json(llm.complete(EDITOR_SYSTEM, prompt, max_tokens=4000))
    idx = int(data["index"])
    if not 0 <= idx < len(candidates):
        raise LLMError(f"Editor picked an invalid story number: {idx}")
    related = [candidates[int(i)] for i in data.get("related", []) if 0 <= int(i) < len(candidates) and int(i) != idx]
    return {"main": candidates[idx], "related": related[:2], "topic": data.get("topic") or candidates[idx]["title"]}


def _parse_post(text: str) -> dict:
    head, sep, body = text.partition("\n===")
    if not sep:
        raise LLMError("Writer reply was not in the expected format")
    meta = {}
    for line in head.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip().upper()] = value.strip()
    tags = [t.strip().lstrip("#") for t in meta.get("TAGS", "").split(",") if t.strip()]
    body = body.lstrip("=").strip()
    if body.startswith("# "):  # drop a duplicated H1 title
        body = body.split("\n", 1)[1].strip() if "\n" in body else ""
    if not meta.get("TITLE") or not body:
        raise LLMError("Writer reply was missing a title or body")
    return {"title": meta["TITLE"].strip('"'), "subtitle": meta.get("SUBTITLE", "").strip('"'), "tags": tags[:5], "body": body}


def write_post(llm, angle_name: str, topic: str, sources: list[dict], profile_text: str, cfg: dict,
               note: dict | None = None) -> dict:
    angle = get_angle(angle_name, cfg)
    blog = cfg["blog"]
    src_block = "\n\n".join(
        f"[{i + 1}] {s['title']} - {s['url']}\n{s.get('text') or '(article text unavailable; use the headline only)'}"
        for i, s in enumerate(sources)
    ) or "(no external sources)"
    note_block = f"\nAUTHOR'S OWN CONTENT (base the post on this):\n{note['content']}\n" if note else ""
    sources_rule = (
        "- Finish with a '## Sources' section listing the sources you used as Markdown links."
        if sources else ""
    )
    prompt = f"""Today's date: {date.today().isoformat()}
Post type: {angle['label']}
{angle['write']}

TOPIC: {topic}
{note_block}
SOURCES:
{src_block}

Requirements:
- {blog.get('words_min', 800)}-{blog.get('words_max', 1500)} words.
- Hook the reader in the first two lines.
- Markdown: ## subheadings, short paragraphs, bullet lists where useful, **bold** for key ideas.
  Do not include an H1 title (it is added separately).
- End with a short takeaway and one question that invites readers to comment.
{sources_rule}

Reply in exactly this format:
TITLE: <catchy but honest title, max 90 characters>
SUBTITLE: <one-sentence subtitle>
TAGS: <5 comma-separated tags, e.g. Artificial Intelligence, Technology, Future>
===
<the post body in Markdown>"""
    system = WRITER_SYSTEM.format(profile=profile_text)
    return _parse_post(llm.complete(system, prompt))


def revise_post(llm, post: dict, instructions: str, profile_text: str) -> dict:
    prompt = f"""Revise this blog post according to the instructions. Keep everything that the instructions
don't ask to change, keep facts accurate, keep the Sources section.

INSTRUCTIONS: {instructions}

CURRENT POST:
TITLE: {post['title']}
SUBTITLE: {post.get('subtitle', '')}
TAGS: {', '.join(post.get('tags', []))}
===
{post['body']}

Reply in exactly the same format (TITLE / SUBTITLE / TAGS / === / body)."""
    return _parse_post(llm.complete(WRITER_SYSTEM.format(profile=profile_text), prompt))
