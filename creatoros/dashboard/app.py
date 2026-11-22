"""Local web dashboard: review posts, approve/edit/publish, write now, edit your profile."""

import re
import threading
from pathlib import Path

import yaml
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from .. import __version__, db, documents, scheduler
from ..config import (EDITABLE_SECTIONS, ROOT, deep_merge, env, load_config, log, read_local_config_text,
                      reset_local_config, save_local_config, write_local_config_text)
from ..modules.blog import pipeline
from ..modules.blog.angles import all_angles
from ..profile import NOTES_DIR, PROFILE_FILE, ensure_profile, list_notes
from ..publishers import PUBLISHERS
from ..settings import validate

STATIC = Path(__file__).parent / "static"


def create_app(cfg: dict, sched=None) -> FastAPI:
    app = FastAPI(title="CreatorOS")
    token = env("DASHBOARD_TOKEN")

    @app.middleware("http")
    async def check_token(request: Request, call_next):
        if token and request.url.path.startswith("/api"):
            if request.headers.get("x-token") != token:
                return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)

    def _bg(fn, *args):
        def run():
            try:
                fn(*args)
            except Exception:
                log.exception("Dashboard task failed")
        threading.Thread(target=run, daemon=True).start()

    def _post(post_id: int) -> dict:
        p = db.get_post(post_id)
        if not p:
            raise HTTPException(404, "post not found")
        return p

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/status")
    def status():
        return {
            "version": __version__,
            "writer": cfg["models"]["writer"], "scout": cfg["models"]["scout"],
            "targets": cfg["publish"]["targets"], "schedule": scheduler.next_runs(sched),
            "telegram": bool(env("TELEGRAM_BOT_TOKEN") and env("TELEGRAM_CHAT_ID")),
            "medium": bool(env("MEDIUM_TOKEN")), "devto": bool(env("DEVTO_API_KEY")),
            "angles": list(all_angles(cfg)), "scheduler_running": sched is not None,
            "mode": "approval" if cfg.get("approval", {}).get("required", True) else "auto",
            "paused": bool(cfg.get("paused")),
        }

    # ------------------------------------------------------------ settings
    def _apply(new_cfg: dict) -> None:
        cfg.clear()
        cfg.update(new_cfg)
        scheduler.reload(sched, cfg)

    @app.get("/api/settings")
    def get_settings():
        return {
            "settings": {k: cfg.get(k) for k in EDITABLE_SECTIONS},
            "angles": all_angles(cfg), "publishers": list(PUBLISHERS),
            "local_yaml": read_local_config_text(),
        }

    @app.put("/api/settings")
    def put_settings(changes: dict = Body(...)):
        changes = {k: v for k, v in changes.items() if k in EDITABLE_SECTIONS}
        errors = validate(deep_merge(cfg, changes))
        if errors:
            raise HTTPException(400, " • ".join(errors))
        _apply(save_local_config(changes))
        return {"ok": True, "schedule": scheduler.next_runs(sched)}

    @app.put("/api/settings/yaml")
    def put_settings_yaml(data: dict = Body(...)):
        try:
            local = yaml.safe_load(data.get("yaml") or "") or {}
        except yaml.YAMLError as e:
            raise HTTPException(400, f"Invalid YAML: {e}")
        if not isinstance(local, dict):
            raise HTTPException(400, "YAML must be a mapping of settings")
        bad = [k for k in local if k not in EDITABLE_SECTIONS]
        if bad:
            raise HTTPException(400, f"These sections can't be set here: {', '.join(bad)}")
        base = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
        errors = validate(deep_merge(base, local))
        if errors:
            raise HTTPException(400, " • ".join(errors))
        write_local_config_text(data.get("yaml") or "")
        _apply(load_config())
        return {"ok": True}

    @app.post("/api/settings/reset")
    def reset_settings():
        _apply(reset_local_config())
        return {"ok": True}

    @app.get("/api/posts")
    def posts(status: str | None = None):
        return db.list_posts(100, status)

    @app.get("/api/posts/{post_id}")
    def post(post_id: int):
        return _post(post_id)

    @app.put("/api/posts/{post_id}")
    def save(post_id: int, data: dict = Body(...)):
        _post(post_id)
        fields = {k: data[k] for k in ("title", "subtitle", "body", "tags") if k in data}
        db.update_post(post_id, **fields)
        pipeline.save_markdown(db.get_post(post_id))
        return {"ok": True}

    @app.post("/api/posts/{post_id}/publish")
    def publish(post_id: int):
        _post(post_id)
        return pipeline.publish_post(cfg, post_id)

    @app.post("/api/posts/{post_id}/reject")
    def reject(post_id: int):
        _post(post_id)
        pipeline.reject(post_id)
        return {"ok": True}

    @app.post("/api/posts/{post_id}/revise")
    def revise(post_id: int, data: dict = Body(...)):
        _post(post_id)
        _bg(pipeline.revise, cfg, post_id, data["instructions"])
        return {"ok": True, "message": "Revising in the background"}

    @app.post("/api/generate")
    def generate(data: dict = Body(...)):
        angle = data.get("angle", "news")
        if angle not in all_angles(cfg):
            raise HTTPException(400, "unknown angle")
        _bg(pipeline.generate_post, cfg, angle, data.get("topic") or None)
        return {"ok": True, "message": "Writing in the background (1-3 minutes)"}

    @app.get("/api/profile")
    def get_profile():
        ensure_profile()
        text =PROFILE_FILE.read_text(encoding="utf-8") if PROFILE_FILE.exists() else ""
        return {"profile": text, "notes": list_notes()}

    @app.put("/api/profile")
    def put_profile(data: dict = Body(...)):
        try:
            yaml.safe_load(data["profile"])
        except yaml.YAMLError as e:
            raise HTTPException(400, f"Invalid YAML: {e}")
        PROFILE_FILE.write_text(data["profile"], encoding="utf-8")
        return {"ok": True}

    # ----------------------------------------------------------- documents
    def _doc(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except documents.DocumentError as e:
            raise HTTPException(400, str(e))

    @app.get("/api/documents")
    def docs_list():
        return documents.list_documents()

    @app.post("/api/documents")
    def docs_upload(data: dict = Body(...)):
        if data.get("data"):
            return _doc(documents.add_document_b64, data.get("filename", ""), data["data"])
        return _doc(documents.create_text_document, data.get("filename", ""), data.get("text", ""))

    @app.get("/api/documents/{name}")
    def docs_get(name: str):
        return {"name": name, "text": _doc(documents.get_text, name)}

    @app.put("/api/documents/{name}")
    def docs_update(name: str, data: dict = Body(...)):
        _doc(documents.update_document, name, text=data.get("text"), enabled=data.get("enabled"))
        return {"ok": True}

    @app.delete("/api/documents/{name}")
    def docs_delete(name: str):
        _doc(documents.delete_document, name)
        return {"ok": True}

    def _note_path(name: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "-", name).strip(".-")
        if not safe.endswith((".md", ".txt")):
            safe += ".md"
        return NOTES_DIR / safe

    @app.put("/api/notes/{name}")
    def put_note(name: str, data: dict = Body(...)):
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        _note_path(name).write_text(data["content"], encoding="utf-8")
        return {"ok": True}

    @app.delete("/api/notes/{name}")
    def delete_note(name: str):
        p = _note_path(name)
        if p.exists():
            p.unlink()
        return {"ok": True}

    return app
