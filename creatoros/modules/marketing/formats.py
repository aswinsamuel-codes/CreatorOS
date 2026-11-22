"""Content formats the marketing agent can plan and write.

kind:
  blog   -> published with the blog publishers (Medium, dev.to, ...)
  social -> published to social targets (LinkedIn, custom platforms)
  draft  -> written for you to use yourself (video scripts, newsletters); nothing is published
"""

FORMATS = {
    "linkedin_post": {
        "label": "LinkedIn post", "kind": "social", "default_targets": ["linkedin"],
        "spec": "LinkedIn post. Plain text (no Markdown). Strong first line that earns the 'see more' click, short "
                "paragraphs, a personal angle or lesson, one clear call to action, 3-5 hashtags at the end. "
                "900-1600 characters.",
    },
    "x_thread": {
        "label": "X / Twitter thread", "kind": "social", "default_targets": [],
        "spec": "X (Twitter) thread of 4-8 posts. Each post under 270 characters, separated by a blank line and "
                "numbered like 1/, 2/ ... Post 1 is a scroll-stopping hook; the last post has the call to action. "
                "At most 2 hashtags in the whole thread.",
    },
    "instagram_caption": {
        "label": "Instagram caption", "kind": "social", "default_targets": [],
        "spec": "Instagram caption. Hook in the first line, short lines with tasteful emojis, value or story in the "
                "middle, call to action (save/share/comment/link in bio), then 10-20 relevant hashtags on the last "
                "line. Also describe the ideal image or carousel in one line starting with 'Visual idea:'.",
    },
    "blog_post": {
        "label": "Blog article", "kind": "blog", "default_targets": None,  # None = blog targets from settings
        "spec": "Blog article in Markdown: ## subheadings, short paragraphs, bullet lists where useful, no H1. "
                "900-1500 words. Practical and search-friendly (use the main keyword naturally in the first "
                "paragraph and a subheading). End with the call to action.",
    },
    "video_script": {
        "label": "Short video script", "kind": "draft", "default_targets": [],
        "spec": "Script for a 45-60 second vertical video (Reel/Short/TikTok). Format:\n"
                "HOOK (0-3s): spoken line + on-screen text\nSCENES: numbered, each with spoken lines, on-screen "
                "text and b-roll idea\nCTA: final line\nThen a suggested caption and 3-5 hashtags.",
    },
    "newsletter": {
        "label": "Newsletter / email", "kind": "draft", "default_targets": [],
        "spec": "Email newsletter section. Start with 'Subject:' (max 60 characters) and 'Preview:' lines, then a "
                "friendly 200-350 word body with one main idea, one link and one call to action.",
    },
}

DEFAULT_BEST_TIMES = {
    # General starting points; tune them in Settings → Advanced (marketing.best_times).
    "linkedin_post": "09:00", "x_thread": "12:30", "instagram_caption": "18:00",
    "blog_post": "10:00", "video_script": "15:00", "newsletter": "08:00",
}


def format_list() -> list[dict]:
    return [{"id": k, "label": v["label"], "kind": v["kind"], "default_targets": v["default_targets"]}
            for k, v in FORMATS.items()]
