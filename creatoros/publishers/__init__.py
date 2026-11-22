"""Publisher plugins. Each one exposes publish(post, cfg) -> url."""

from . import devto, linkedin, markdown_file, medium, youtube

PUBLISHERS = {
    "medium": medium.publish,
    "devto": devto.publish,
    "linkedin": linkedin.publish,
    "youtube": youtube.publish,
    "markdown": markdown_file.publish,
}


def is_target(target: str) -> bool:
    from .. import connections
    if target.startswith("custom:"):
        return target[7:] in connections.list_custom()
    return target in PUBLISHERS


def publish_to(target: str, post: dict, cfg: dict) -> str:
    if target.startswith("custom:"):
        from .webhook import publish_custom
        return publish_custom(target[7:], post)
    if target not in PUBLISHERS:
        raise ValueError(f"Unknown publish target '{target}'. Available: {', '.join(PUBLISHERS)}")
    return PUBLISHERS[target](post, cfg.get("publish", {}).get(target, {}))
