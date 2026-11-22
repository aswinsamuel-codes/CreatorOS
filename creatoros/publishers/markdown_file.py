"""Saves the published post as a Markdown file (useful for testing or static sites)."""

import re

from ..config import BLOG_OUTPUT


def publish(post: dict, opts: dict) -> str:
    out = BLOG_OUTPUT / "published"
    out.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", post["title"].lower()).strip("-")[:60]
    path = out / f"{post['id']:04d}-{slug}.md"
    path.write_text(
        f"---\ntitle: \"{post['title']}\"\ndescription: \"{post.get('subtitle', '')}\"\n"
        f"tags: [{', '.join(post.get('tags', []))}]\n---\n\n{post['body']}\n",
        encoding="utf-8",
    )
    return path.as_uri()
