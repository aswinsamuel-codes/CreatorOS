"""Post types. Each angle tells the editor what story to pick and the writer how to write it."""

ANGLES = {
    "news": {
        "label": "Tech news explainer",
        "pick": "Pick the most surprising, important or 'crazy' tech story right now - something people in tech will talk about today.",
        "write": (
            "Explain what happened, why it matters, who it affects and what is likely to happen next. "
            "Give technical readers the real substance, but keep it readable for people from other fields."
        ),
    },
    "future": {
        "label": "Future of tech (question-led)",
        "pick": "Pick a story that hints at where technology is heading in the next 5-10 years.",
        "write": (
            "Build the post around one big question about the future (e.g. 'Will AI agents replace apps by 2030?'). "
            "Explore 2-3 realistic scenarios, give a clear prediction with reasoning, and say what readers should "
            "watch for. Ask readers a direct question at the end to start a discussion."
        ),
    },
    "business": {
        "label": "Business opportunities",
        "pick": "Pick a trend or story that opens up new business, startup or career opportunities.",
        "write": (
            "Analyse which businesses, startups, jobs and skills will boom (or decline) because of this trend. "
            "Give concrete, actionable suggestions: ideas to build, who should act now, rough market signals, "
            "and the risks. Be specific, not generic. Do not give personalised financial or investment advice."
        ),
    },
    "fun": {
        "label": "Fun / weird tech",
        "pick": "Pick the most fun, weird or jaw-dropping tech story - something people will share.",
        "write": "Keep it playful and casual, with humour, but stay accurate.",
    },
    "personal": {
        "label": "From the author's own content",
        "pick": "",
        "write": (
            "Turn the author's own notes (below) into a polished post in their voice, first person. "
            "Keep their real experiences and opinions; add structure, clarity and lessons readers can use. "
            "Don't invent experiences they didn't describe."
        ),
    },
}


def all_angles(cfg: dict | None = None) -> dict:
    """Built-in angles plus any custom ones from config (blog.angles). Custom entries
    with the same name override the built-in ones."""
    custom = ((cfg or {}).get("blog") or {}).get("angles") or {}
    merged = {k: dict(v) for k, v in ANGLES.items()}
    for name, spec in custom.items():
        merged[name] = {**merged.get(name, {"label": name, "pick": "", "write": ""}), **(spec or {})}
    return merged


def get_angle(name: str, cfg: dict | None = None) -> dict:
    angles = all_angles(cfg)
    if name not in angles:
        raise ValueError(f"Unknown angle '{name}'. Choose from: {', '.join(angles)}")
    return angles[name]
