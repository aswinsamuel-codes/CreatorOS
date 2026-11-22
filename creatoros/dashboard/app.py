"""Local web dashboard: review posts, approve/edit/publish, write now, edit your profile."""

import os
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import yaml
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from .. import __version__, connections, db, documents, notify, scheduler
from ..modules.marketing import content as marketing_content
from ..modules.marketing import planner
from ..modules.marketing.formats import FORMATS, format_list
from ..modules.social import folder as folder_mod
from ..modules.video import posting, videoinfo
from ..personas import list_personas
from ..publishers import linkedin, youtube

OAUTH = {"linkedin": linkedin, "youtube": youtube}
from ..config import (EDITABLE_SECTIONS, ROOT, deep_merge, env, load_config, log, read_local_config_text,
                      reset_local_config, save_local_config, write_local_config_text)
from ..modules.blog import pipeline
from ..modules.blog.angles import all_angles
from ..profile import NOTES_DIR, PROFILE_FILE, ensure_profile, list_notes
from ..publishers import PUBLISHERS, is_target
from ..settings import validate

STATIC = Path(__file__).parent / "static"


def create_app(cfg: dict, sched=None) -> FastAPI:
    app = FastAPI(title="CreatorOS")
    token = env("DASHBOARD_TOKEN")

    # Browser redirects (OAuth) can't send the x-token header; the callback is protected by `state`.
    OPEN_PATHS = tuple(f"/api/connections/{p}/{step}" for p in OAUTH for step in ("start", "callback"))

    @app.middleware("http")
    async def check_token(request: Request, call_next):
        if token and request.url.path.startswith("/api") and request.url.path not in OPEN_PATHS:
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
            "angles": all_angles(cfg),
            "publishers": list(PUBLISHERS) + [f"custom:{cid}" for cid in connections.list_custom()],
            "publisher_names": {f"custom:{cid}": s["name"] for cid, s in connections.list_custom().items()},
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
        if isinstance(data.get("meta"), dict):
            fields["meta"] = {**(_post(post_id).get("meta") or {}), **data["meta"]}
        db.update_post(post_id, **fields)
        pipeline.save_markdown(db.get_post(post_id))
        return {"ok": True}

    @app.post("/api/posts/{post_id}/approve")
    def approve(post_id: int):
        _post(post_id)
        return {"status": pipeline.approve(cfg, post_id)}

    @app.post("/api/posts/{post_id}/publish")
    def publish(post_id: int):
        _post(post_id)
        return pipeline.publish_post(cfg, post_id)

    # --------------------------------------------------------- connections
    @app.get("/api/connections")
    def connections_list(request: Request):
        out = []
        for pid, p in connections.PLATFORMS.items():
            fields = []
            for f in p["fields"]:
                in_env = bool(os.environ.get(f["name"], "").strip())
                value = env(f["name"])
                secret = f.get("secret", True)
                fields.append({**f, "secret": secret, "set": bool(value), "source": "env" if in_env else "dashboard",
                               "masked": connections.mask(value) if secret else (value or "")})
            ready = all(x["set"] for x in fields)
            item = {"id": pid, **p, "fields": fields, "ready": ready, "connected": ready}
            if p.get("ai"):
                item["uses"] = [role for role in ("writer", "scout") if cfg["models"][role].get("provider") == pid]
            if pid in OAUTH:
                item["oauth"] = OAUTH[pid].status()
                item["connected"] = item["oauth"].get("connected", False)
                item["redirect_uri"] = OAUTH[pid].redirect_uri(str(request.base_url))
            out.append(item)
        custom = [{"id": cid, **{k: v for k, v in spec.items() if k != "api_key"},
                   "has_key": bool(spec.get("api_key")), "target": f"custom:{cid}"}
                  for cid, spec in connections.list_custom().items()]
        return {"platforms": out, "custom": custom}

    # Custom platforms (registered before the generic /{platform} routes).
    @app.post("/api/connections/custom")
    def custom_save(data: dict = Body(...)):
        try:
            cid = connections.save_custom(data.get("id") or None, data)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {"ok": True, "id": cid}

    @app.delete("/api/connections/custom/{cid}")
    def custom_delete(cid: str):
        connections.delete_custom(cid)
        return {"ok": True}

    @app.post("/api/connections/custom/{cid}/test")
    def custom_test(cid: str):
        from ..publishers.webhook import test_custom
        try:
            return {"ok": True, "message": test_custom(cid)}
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.put("/api/connections/{platform}")
    def connections_save(platform: str, data: dict = Body(...)):
        if platform not in connections.PLATFORMS:
            raise HTTPException(404, "unknown platform")
        connections.set_many({k: v for k, v in (data.get("values") or {}).items() if k in connections.ALLOWED_FIELDS
                              and k in {f["name"] for f in connections.PLATFORMS[platform]["fields"]}})
        notify.reset()
        return {"ok": True}

    @app.post("/api/connections/{platform}/remove")
    def connections_remove(platform: str):
        """Forget a platform: dashboard-saved keys, its OAuth login, and matching lines in .env."""
        if platform not in connections.PLATFORMS:
            raise HTTPException(404, "unknown platform")
        names = [f["name"] for f in connections.PLATFORMS[platform]["fields"]]
        connections.set_many({n: "" for n in names})
        if platform in OAUTH:
            OAUTH[platform].disconnect()
        env_file = ROOT / ".env"
        if env_file.exists():
            lines = env_file.read_text(encoding="utf-8").splitlines()
            env_file.write_text("\n".join(
                f"{ln.split('=', 1)[0]}=" if ln.split("=", 1)[0].strip() in names else ln for ln in lines) + "\n",
                encoding="utf-8")
        for n in names:
            os.environ.pop(n, None)
        notify.reset()
        in_use = [r for r in ("writer", "scout") if cfg["models"][r].get("provider") == platform]
        return {"ok": True, "in_use": in_use}

    @app.get("/api/usage")
    def usage():
        now = datetime.now()
        month = db.usage_summary(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat())
        today = db.usage_summary(now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat())
        budgets = (cfg.get("usage") or {}).get("monthly_budget_tokens") or {}
        out = {}
        for p in set(cfg.get("providers", {})) | set(month):
            m = month.get(p, {"input": 0, "output": 0, "calls": 0})
            total = m["input"] + m["output"]
            budget = int(budgets.get(p) or 2000000)
            out[p] = {**m, "total": total, "budget": budget, "percent": round(min(total / budget * 100, 999), 1),
                      "today": sum(today.get(p, {}).get(k, 0) for k in ("input", "output"))}
        return out

    @app.put("/api/usage/budget")
    def usage_budget(data: dict = Body(...)):
        provider, tokens = data.get("provider"), int(data.get("tokens") or 0)
        if provider not in cfg.get("providers", {}) or tokens < 1000:
            raise HTTPException(400, "Budget must be at least 1,000 tokens")
        _apply(save_local_config({"usage": {"monthly_budget_tokens": {provider: tokens}}}))
        return {"ok": True}

    AI_PROVIDERS = ("claude", "openai", "gemini")

    @app.get("/api/connections/{platform}/models")
    def ai_models(platform: str):
        from ..llm import list_models
        if platform not in AI_PROVIDERS:
            raise HTTPException(404, "not an AI provider")
        try:
            models = list_models(cfg, platform)
        except Exception as e:
            raise HTTPException(400, str(e))
        return {"models": models, "writer": cfg["models"]["writer"], "scout": cfg["models"]["scout"]}

    @app.post("/api/connections/{platform}/use")
    def ai_use(platform: str, data: dict = Body(...)):
        if platform not in AI_PROVIDERS or platform not in cfg.get("providers", {}):
            raise HTTPException(404, "not an AI provider")
        role, model = data.get("role"), (data.get("model") or "").strip()
        if role not in ("writer", "scout") or not model:
            raise HTTPException(400, "Choose a model and a role")
        spec = {"provider": platform, "model": model}
        if platform == "claude":
            spec["effort"] = "medium" if role == "writer" else "low"
        new = save_local_config({"models": {role: spec}})
        if platform != "claude":  # effort only applies to Claude
            new["models"][role].pop("effort", None)
        _apply(new)
        return {"ok": True, "models": cfg["models"]}

    @app.post("/api/connections/telegram/detect")
    def telegram_detect():
        from ..notify.telegram import find_chat_ids
        token = env("TELEGRAM_BOT_TOKEN")
        if not token:
            raise HTTPException(400, "Save your bot token first")
        try:
            chats = find_chat_ids(token)
        except Exception as e:
            raise HTTPException(400, f"Telegram said: {e}")
        if not chats:
            raise HTTPException(400, "No messages yet. Open your bot in Telegram, send it 'hi', then try again.")
        return {"chats": [{"id": cid, "name": name} for cid, name in chats]}

    @app.post("/api/connections/{platform}/test")
    def connections_test(platform: str):
        try:
            return {"ok": True, "message": _test_platform(platform)}
        except Exception as e:
            raise HTTPException(400, str(e))

    def _test_platform(platform: str) -> str:
        import requests as rq
        if platform == "claude":
            import anthropic
            key = env("ANTHROPIC_API_KEY")
            if not key:
                raise RuntimeError("Save your API key first")
            from ..llm import friendly_claude_error
            client = anthropic.Anthropic(api_key=key)
            try:
                # A 1-token request to the cheapest model (a tiny fraction of a cent) also proves the
                # account has credits, which a key check alone doesn't.
                client.messages.create(model=cfg["models"]["scout"]["model"] if cfg["models"]["scout"]["provider"] == "claude"
                                       else "claude-haiku-5-5", max_tokens=1,
                                       messages=[{"role": "user", "content": "hi"}])
            except anthropic.AuthenticationError:
                raise RuntimeError("Claude rejected this key - check it was copied completely")
            except anthropic.APIStatusError as e:
                raise RuntimeError(friendly_claude_error(e.status_code, str(e.message)))
            return "Claude key works and your account has credits ✔"
        if platform in ("openai", "gemini"):
            from ..llm import OpenAICompatibleLLM, cheapest, list_models
            prov = cfg["providers"][platform]
            if not env(prov.get("api_key_env")):
                raise RuntimeError("Save your API key first")
            models = list_models(cfg, platform)
            model = cheapest(models)
            if not model:
                raise RuntimeError("Key works, but no chat models are available on this account")
            # A tiny request proves the key has quota/credits, not just that it exists.
            OpenAICompatibleLLM(model, prov["base_url"], env(prov.get("api_key_env"))).complete("Reply OK.", "hi", max_tokens=16)
            return f"{connections.PLATFORMS[platform]['label']} works ✔ ({len(models)} models available)"
        if platform == "telegram":
            from ..notify.telegram import Telegram
            if not env("TELEGRAM_BOT_TOKEN"):
                raise RuntimeError("Save your bot token first")
            bot = Telegram(env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID") or "")
            me = bot.api("getMe")
            if env("TELEGRAM_CHAT_ID"):
                bot.send_text("✅ CreatorOS is connected to this chat.")
                return f"@{me['username']} works - check Telegram for a test message ✔"
            return f"@{me['username']} works - now click 'Find my chat ID'"
        if platform == "medium":
            from ..publishers import medium
            return f"Connected to Medium as @{medium.me().get('username')} ✔"
        if platform == "devto":
            r = rq.get("https://dev.to/api/users/me", headers={"api-key": env("DEVTO_API_KEY") or ""}, timeout=20)
            if r.status_code != 200:
                raise RuntimeError("dev.to rejected this key")
            return f"Connected to dev.to as @{r.json().get('username')} ✔"
        if platform in OAUTH:
            s = OAUTH[platform].status()
            if not s.get("connected"):
                raise RuntimeError("Not connected yet - click Connect")
            return f"Connected as {s.get('name')} ✔"
        raise RuntimeError("unknown platform")

    def _oauth(platform: str):
        if platform not in OAUTH:
            raise HTTPException(404, "unknown platform")
        return OAUTH[platform]

    @app.get("/api/connections/{platform}/start")
    def oauth_start(platform: str, request: Request):
        try:
            return RedirectResponse(_oauth(platform).auth_url(str(request.base_url)))
        except RuntimeError as e:
            return RedirectResponse(f"/?error={quote(str(e))}")

    @app.get("/api/connections/{platform}/callback")
    def oauth_callback(platform: str, request: Request, code: str = "", state: str = "", error: str = "",
                       error_description: str = ""):
        if error:
            return RedirectResponse(f"/?error={quote(error_description or error)}")
        try:
            info = _oauth(platform).finish_auth(code, state, str(request.base_url))
        except Exception as e:
            log.error("%s connect failed: %s", platform, e)
            return RedirectResponse(f"/?error={quote(str(e))}")
        return RedirectResponse(f"/?connected={quote(info.get('name') or info.get('channel') or platform)}")

    @app.post("/api/connections/{platform}/disconnect")
    def oauth_disconnect(platform: str):
        _oauth(platform).disconnect()
        return {"ok": True}

    # ----------------------------------------------------------- marketing
    @app.get("/api/marketing/formats")
    def marketing_formats():
        return {"formats": format_list(),
                "targets": [{"id": t, "name": n} for t, n in
                            [("linkedin", "LinkedIn"), ("medium", "Medium"), ("devto", "dev.to"), ("markdown", "Markdown file")] +
                            [(f"custom:{cid}", s["name"]) for cid, s in connections.list_custom().items()]]}

    @app.get("/api/campaigns")
    def campaigns_list():
        out = []
        for c in db.list_campaigns():
            items = db.list_calendar(c["id"])
            out.append({**c, "total": len(items), "done": sum(i["status"] == "drafted" for i in items)})
        return out

    @app.post("/api/campaigns")
    def campaigns_create(data: dict = Body(...)):
        if not (data.get("goal") or "").strip():
            raise HTTPException(400, "Describe the campaign goal")
        formats = [f for f in data.get("formats") or [] if f in FORMATS]
        if not formats:
            raise HTTPException(400, "Pick at least one content format")
        targets = {f: [t for t in ts if is_target(t)] for f, ts in (data.get("targets") or {}).items() if f in FORMATS}
        brief = {k: data.get(k) for k in ("goal", "audience", "message", "links", "notes", "start", "weeks",
                                           "per_week", "role", "custom_role")}
        brief.update(formats=formats, targets=targets)
        cid = db.create_campaign((data.get("name") or data["goal"])[:80], brief)
        _bg(planner.plan_campaign, cfg, cid)
        return {"ok": True, "id": cid, "message": "Planning your campaign (about 1 minute)…"}

    def _campaign(cid: int) -> dict:
        c = db.get_campaign(cid)
        if not c:
            raise HTTPException(404, "campaign not found")
        return c

    @app.get("/api/campaigns/{cid}")
    def campaign_get(cid: int):
        return {**_campaign(cid), "calendar": db.list_calendar(cid)}

    @app.post("/api/campaigns/{cid}/status")
    def campaign_status(cid: int, data: dict = Body(...)):
        _campaign(cid)
        if data.get("status") not in ("active", "paused"):
            raise HTTPException(400, "status must be active or paused")
        db.update_campaign(cid, status=data["status"])
        return {"ok": True}

    @app.delete("/api/campaigns/{cid}")
    def campaign_delete(cid: int):
        _campaign(cid)
        db.delete_campaign(cid)
        return {"ok": True}

    @app.post("/api/campaigns/{cid}/write-week")
    def campaign_write_week(cid: int):
        _campaign(cid)
        horizon = (datetime.now() + timedelta(days=7)).isoformat(timespec="seconds")
        items = [i for i in db.list_calendar(cid) if i["status"] in ("planned", "failed") and i["due"] <= horizon]

        def run():
            for i in items:
                try:
                    marketing_content.write_item(cfg, i["id"])
                except Exception:
                    pass
        _bg(run)
        return {"ok": True, "message": f"Writing {len(items)} piece(s) for the next 7 days…"}

    def _item(item_id: int) -> dict:
        i = db.get_calendar_item(item_id)
        if not i:
            raise HTTPException(404, "item not found")
        return i

    @app.post("/api/calendar/{item_id}/write")
    def calendar_write(item_id: int):
        _item(item_id)
        _bg(marketing_content.write_item, cfg, item_id)
        return {"ok": True, "message": "Writing…"}

    @app.post("/api/calendar/{item_id}/skip")
    def calendar_skip(item_id: int):
        _item(item_id)
        db.update_calendar_item(item_id, status="skipped")
        return {"ok": True}

    @app.put("/api/calendar/{item_id}")
    def calendar_update(item_id: int, data: dict = Body(...)):
        _item(item_id)
        fields = {k: str(data[k])[:300] for k in ("topic", "hook", "cta", "pillar") if k in data}
        if data.get("due"):
            try:
                fields["due"] = datetime.fromisoformat(data["due"]).isoformat(timespec="seconds")
            except ValueError:
                raise HTTPException(400, "Invalid date/time")
        if data.get("status") == "planned":
            fields["status"] = "planned"
        db.update_calendar_item(item_id, **fields)
        return {"ok": True}

    @app.post("/api/posts/{post_id}/repurpose")
    def post_repurpose(post_id: int, data: dict = Body(...)):
        _post(post_id)
        formats = [f for f in data.get("formats") or [] if f in FORMATS]
        if not formats:
            raise HTTPException(400, "Pick at least one format")
        _bg(marketing_content.repurpose, cfg, post_id, formats, data.get("targets"), data.get("instructions", ""))
        return {"ok": True, "message": f"Creating {len(formats)} new version(s)…"}

    # --------------------------------------------------------------- video
    @app.post("/api/video/scan")
    def video_scan(data: dict = Body(...)):
        try:
            files = videoinfo.scan(data.get("path", ""))
            infos = [{"name": f.name, **videoinfo.probe(f)} for f in files[:50]]
        except (FileNotFoundError, RuntimeError) as e:
            raise HTTPException(400, str(e))
        return {"count": len(files), "videos": infos}

    @app.post("/api/video/run")
    def video_run(data: dict = Body(...)):
        try:
            videoinfo.scan(data.get("path", ""))
            videoinfo.require_ffmpeg()
        except (FileNotFoundError, RuntimeError) as e:
            raise HTTPException(400, str(e))
        targets = [t for t in data.get("targets", []) if t in ("youtube", "linkedin") or
                   (t.startswith("custom:") and is_target(t))] or ["youtube"]
        yt_defaults = cfg.get("publish", {}).get("youtube", {})
        _bg(posting.create_posts, cfg, data["path"], data.get("instructions", ""), targets,
            data.get("privacy") or yt_defaults.get("privacy", "private"),
            str(data.get("category_id") or yt_defaults.get("category_id", "28")),
            float(data.get("interval_hours") or 24), data.get("start_at") or None,
            bool(data.get("transcribe", True)), True, data.get("role") or None, data.get("custom_role"))
        return {"ok": True, "message": "Inspecting your video(s) and writing titles and descriptions (about 30-90 s each)"}

    # ------------------------------------------------------ personas/folder
    @app.get("/api/personas")
    def personas_list():
        return {"personas": list_personas(), "current": cfg.get("persona") or {}}

    @app.post("/api/folder/scan")
    def folder_scan(data: dict = Body(...)):
        try:
            files = folder_mod.scan(data.get("folder", ""))
        except FileNotFoundError as e:
            raise HTTPException(400, str(e))
        return {"count": len(files), "files": [f.name for f in files]}

    @app.post("/api/folder/run")
    def folder_run(data: dict = Body(...)):
        try:
            folder_mod.scan(data.get("folder", ""))
        except FileNotFoundError as e:
            raise HTTPException(400, str(e))
        targets = [t for t in data.get("targets", []) if is_target(t)] or ["linkedin"]
        _bg(folder_mod.create_posts, cfg, data["folder"], data.get("instructions", ""), targets,
            data.get("mode", "combined"), float(data.get("interval_hours") or 24), data.get("start_at") or None,
            True, data.get("role") or None, data.get("custom_role"))
        return {"ok": True, "message": "Inspecting your files and writing posts (about 10-30 s per file)"}

    @app.get("/api/media")
    def media(path: str):
        p = Path(path).resolve()
        if folder_mod.MEDIA_DIR.resolve() not in p.parents or not p.is_file():
            raise HTTPException(404, "not found")
        return FileResponse(p)

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
