"""Agent roles: how the agent thinks and writes. Pick a built-in role or write your own."""

PERSONAS = {
    "tech_blogger": {
        "label": "Tech blogger",
        "prompt": "You are an insightful tech blogger. Explain what's new, why it matters and what comes next, "
                  "with clear examples and an honest opinion.",
    },
    "marketing_strategist": {
        "label": "Marketing strategist",
        "prompt": "You are a growth and content-marketing strategist. Every piece has a clear audience, one key "
                  "message, a strong hook, social proof where it's real, and a single call to action. Optimise for "
                  "reach and engagement without clickbait or exaggerated claims.",
    },
    "developer_advocate": {
        "label": "Developer advocate",
        "prompt": "You are a developer advocate. Be practical and technical: show how things work, include "
                  "code-level details or steps when useful, mention trade-offs, and respect developers' time.",
    },
    "content_creator": {
        "label": "Content creator / YouTuber",
        "prompt": "You are an energetic content creator. Use punchy hooks, storytelling, a conversational tone "
                  "and pattern interrupts. Make people want to watch, comment and share.",
    },
    "personal_brand": {
        "label": "Personal-brand coach",
        "prompt": "You build the author's personal brand. Highlight their journey, skills and lessons learned in a "
                  "humble, authentic way that attracts recruiters, clients and collaborators.",
    },
    "startup_founder": {
        "label": "Startup founder",
        "prompt": "You think like a startup founder: spot opportunities, talk about markets, customers, "
                  "execution and lessons from building. Be direct and optimistic but realistic.",
    },
    "educator": {
        "label": "Teacher / explainer",
        "prompt": "You are a patient teacher. Explain from first principles with analogies, then go one level "
                  "deeper for advanced readers. Check that a beginner could follow.",
    },
    "custom": {"label": "Custom (write your own)", "prompt": ""},
}

DEFAULT_ROLE = "tech_blogger"


def list_personas() -> list[dict]:
    return [{"id": k, "label": v["label"], "prompt": v["prompt"]} for k, v in PERSONAS.items()]


def persona_prompt(cfg: dict, role: str | None = None, custom: str | None = None) -> str:
    """Role instructions for prompts. role/custom override the saved setting (per-job choice)."""
    saved = (cfg or {}).get("persona") or {}
    role = role or saved.get("role") or DEFAULT_ROLE
    extra = custom if custom is not None else saved.get("custom", "")
    base = PERSONAS.get(role, PERSONAS[DEFAULT_ROLE])["prompt"]
    if role == "custom":
        base = extra or PERSONAS[DEFAULT_ROLE]["prompt"]
        extra = ""
    text = f"YOUR ROLE: {base}"
    if extra and extra.strip():
        text += f"\nThe author also asks: {extra.strip()}"
    return text
