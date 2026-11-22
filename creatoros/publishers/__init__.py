"""Publisher plugins. Each one exposes publish(post, cfg) -> url."""

from . import devto, linkedin, markdown_file, medium

PUBLISHERS = {
    "medium": medium.publish,
    "devto": devto.publish,
    "linkedin": linkedin.publish,
    "markdown": markdown_file.publish,
}


def publish_to(target: str, post: dict, cfg: dict) -> str:
    if target not in PUBLISHERS:
        raise ValueError(f"Unknown publish target '{target}'. Available: {', '.join(PUBLISHERS)}")
    return PUBLISHERS[target](post, cfg.get("publish", {}).get(target, {}))
