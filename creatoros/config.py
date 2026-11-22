import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# APP_DIR: where the code and bundled defaults live (config.yaml, profile template).
# ROOT (home): where YOUR data lives. Same folder normally; the desktop app sets
# CREATOROS_HOME to your user app-data folder so the data survives app updates.
APP_DIR = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CREATOROS_HOME") or APP_DIR)
WORKSPACE = ROOT / "workspace"
BLOG_OUTPUT = WORKSPACE / "output" / "blog"
PROFILE_DIR = ROOT / "profile"
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"

log = logging.getLogger("creatoros")


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_DIR / "creatoros.log", encoding="utf-8"),
        ],
    )
    for noisy in ("apscheduler", "httpx", "httpx2", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# In Docker this points into the data volume so your settings survive container rebuilds.
LOCAL_CONFIG = Path(os.environ.get("CREATOROS_LOCAL_CONFIG") or ROOT / "config.local.yaml")

# Sections the dashboard is allowed to change (secrets always stay in .env).
EDITABLE_SECTIONS = ("models", "providers", "blog", "approval", "publish", "dashboard", "timezone", "paused",
                     "persona", "marketing", "usage")


def deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base. Dicts merge recursively; lists and values replace."""
    out = dict(base)
    for k, v in (override or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(path: str | None = None) -> dict:
    """config.yaml holds the documented defaults; config.local.yaml (written by the
    dashboard, ignored by git) holds your personal changes on top."""
    load_dotenv(ROOT / ".env")
    base = _read_yaml(Path(path) if path else APP_DIR / "config.yaml")
    return deep_merge(base, _read_yaml(LOCAL_CONFIG))


def save_local_config(changes: dict) -> dict:
    """Merge changes into config.local.yaml and return the new full config."""
    changes = {k: v for k, v in changes.items() if k in EDITABLE_SECTIONS}
    local = deep_merge(_read_yaml(LOCAL_CONFIG), changes)
    with open(LOCAL_CONFIG, "w", encoding="utf-8") as f:
        f.write("# Your personal settings (written by the CreatorOS dashboard).\n"
                "# Anything here overrides config.yaml. Delete this file to reset to defaults.\n")
        yaml.safe_dump(local, f, sort_keys=False, allow_unicode=True)
    return load_config()


def read_local_config_text() -> str:
    return LOCAL_CONFIG.read_text(encoding="utf-8") if LOCAL_CONFIG.exists() else ""


def write_local_config_text(text: str) -> None:
    LOCAL_CONFIG.write_text(text, encoding="utf-8")


def reset_local_config() -> dict:
    if LOCAL_CONFIG.exists():
        LOCAL_CONFIG.unlink()
    return load_config()


def env(name: str | None, default: str | None = None) -> str | None:
    """A secret/setting from .env, falling back to keys saved on the dashboard's Connections tab."""
    if not name:
        return default
    value = os.environ.get(name, "").strip()
    if value:
        return value
    from . import connections
    return connections.get(name) or default
