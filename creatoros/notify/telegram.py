"""Telegram approval bot (plain Bot API over HTTPS, no extra library)."""

import html
import time

import requests

from ..config import env, log


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = str(chat_id)
        self.awaiting_edit: int | None = None  # post id waiting for edit instructions

    @classmethod
    def from_env(cls) -> "Telegram | None":
        token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
        return cls(token, chat) if token and chat else None

    # ----------------------------------------------------------------- API
    def api(self, method: str, timeout: int = 30, files=None, **params):
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        if files:
            r = requests.post(url, data=params, files=files, timeout=timeout)
        else:
            r = requests.post(url, json=params, timeout=timeout)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method} failed: {data.get('description')}")
        return data["result"]

    def send_text(self, text: str, **extra):
        return self.api("sendMessage", chat_id=self.chat_id, text=text[:4000], parse_mode="HTML",
                        disable_web_page_preview=True, **extra)

    # ----------------------------------------------------------- messages
    def send_photos(self, media: list[dict]) -> None:
        """Send up to 10 images as an album (Telegram's limit)."""
        from pathlib import Path
        import json as _json

        items = [m for m in media if Path(m["path"]).exists()][:10]
        if not items:
            return
        if len(items) == 1:
            with open(items[0]["path"], "rb") as f:
                self.api("sendPhoto", chat_id=self.chat_id, files={"photo": f}, timeout=60)
            return
        files = {f"p{i}": open(m["path"], "rb") for i, m in enumerate(items)}
        try:
            album = [{"type": "photo", "media": f"attach://p{i}"} for i in range(len(items))]
            self.api("sendMediaGroup", chat_id=self.chat_id, media=_json.dumps(album), files=files, timeout=120)
        finally:
            for f in files.values():
                f.close()

    def send_for_approval(self, post: dict) -> None:
        e = html.escape
        if post.get("kind") == "video":
            meta = post.get("meta") or {}
            thumbs = [{"path": m["thumb"]} for m in post.get("media") or [] if m.get("thumb")]
            try:
                self.send_photos(thumbs)
            except Exception as ex:
                log.warning("Could not send thumbnail: %s", ex)
            when = (post.get("scheduled_at") or "").replace("T", " ")
            kind = "Short" if (meta.get("youtube") or {}).get("short") else "video"
            text = (
                f"🎬 <b>New {kind} #{post['id']}</b> → {e(', '.join(post.get('targets') or []))}"
                f" · {int(meta.get('duration', 0))}s · scheduled {e(when)}\n\n"
                f"<b>{e(post['title'])}</b>\n\n<b>YouTube description:</b>\n{e(post['body'][:1500])}\n\n"
                f"<b>LinkedIn caption:</b>\n{e((meta.get('linkedin_text') or '')[:1200])}"
            )
        elif post.get("kind") == "social":
            try:
                self.send_photos(post.get("media") or [])
            except Exception as ex:
                log.warning("Could not send preview images: %s", ex)
            when = (post.get("scheduled_at") or "").replace("T", " ")
            text = (
                f"📣 <b>New {e('/'.join(post.get('targets') or ['social']))} post #{post['id']}</b> "
                f"({len(post.get('media') or [])} images{', scheduled ' + e(when) if when else ''})\n\n"
                f"{e(post['body'][:3000])}"
            )
        else:
            preview = post["body"][:1500].rsplit("\n", 1)[0]
            text = (
                f"📝 <b>New post #{post['id']}</b> ({e(post['angle'])})\n\n"
                f"<b>{e(post['title'])}</b>\n<i>{e(post.get('subtitle') or '')}</i>\n"
                f"Tags: {e(', '.join(post.get('tags', [])))}\n\n"
                f"{e(preview)}\n\n…"
            )
        pid = post["id"]
        keyboard = {"inline_keyboard": [
            [{"text": "✅ Publish", "callback_data": f"approve:{pid}"},
             {"text": "❌ Skip", "callback_data": f"reject:{pid}"}],
            [{"text": "✏️ Edit", "callback_data": f"edit:{pid}"},
             {"text": "📄 Full text", "callback_data": f"full:{pid}"}],
        ]}
        self.send_text(text, reply_markup=keyboard)

    def send_full(self, post: dict) -> None:
        doc = f"# {post['title']}\n\n*{post.get('subtitle', '')}*\n\n{post['body']}".encode("utf-8")
        self.api("sendDocument", chat_id=self.chat_id, caption=f"Post #{post['id']}",
                 files={"document": (f"post-{post['id']}.md", doc)}, timeout=60)

    def send_published(self, post: dict) -> None:
        links = "\n".join(f"• {k}: {v}" for k, v in (post.get("published") or {}).items())
        msg = f"🚀 <b>Published #{post['id']}</b>: {html.escape(post['title'])}\n{html.escape(links)}"
        if post.get("error"):
            msg += f"\n⚠️ {html.escape(post['error'])}"
        self.send_text(msg)

    # ------------------------------------------------------------- polling
    def poll_forever(self, cfg: dict) -> None:
        """Listen for button presses and edit instructions. Runs in a background thread."""
        from .. import db
        from ..modules.blog import pipeline

        offset = None
        log.info("Telegram bot listening")
        while True:
            try:
                params = {"timeout": 50, "allowed_updates": ["message", "callback_query"]}
                if offset:
                    params["offset"] = offset
                updates = self.api("getUpdates", timeout=60, **params)
            except Exception as e:
                log.warning("Telegram polling error: %s", e)
                time.sleep(10)
                continue
            for up in updates:
                offset = up["update_id"] + 1
                try:
                    self._handle(up, cfg, db, pipeline)
                except Exception as e:
                    log.exception("Telegram handler error")
                    self.send_text(f"⚠️ Error: {html.escape(str(e))}")

    @staticmethod
    def _mode_text(cfg: dict) -> str:
        mode = "🤝 APPROVAL (I ask before posting)" if cfg.get("approval", {}).get("required", True) \
            else "🤖 AUTO (I post on my own)"
        state = "⏸ paused" if cfg.get("paused") else "▶️ running"
        return f"Mode: <b>{mode}</b>\nSchedule: <b>{state}</b>"

    def _handle(self, up: dict, cfg: dict, db, pipeline) -> None:
        if "callback_query" in up:
            cq = up["callback_query"]
            if str(cq["message"]["chat"]["id"]) != self.chat_id:
                return
            self.api("answerCallbackQuery", callback_query_id=cq["id"])
            action, _, pid = cq["data"].partition(":")
            post_id = int(pid)
            post = db.get_post(post_id)
            if not post:
                self.send_text(f"Post #{post_id} not found.")
            elif action == "approve":
                if post["status"] in ("published", "scheduled"):
                    self.send_text(f"#{post_id} is already {post['status']}.")
                else:
                    self.send_text(f"Approving #{post_id}…")
                    pipeline.approve(cfg, post_id)
            elif action == "reject":
                pipeline.reject(post_id)
                self.send_text(f"Skipped #{post_id}.")
            elif action == "full":
                self.send_full(post)
            elif action == "edit":
                self.awaiting_edit = post_id
                self.send_text(f"✏️ Send me your changes for #{post_id} (e.g. \"make it more casual, shorter title\").")
            return

        msg = up.get("message") or {}
        if str(msg.get("chat", {}).get("id")) != self.chat_id or not msg.get("text"):
            return
        text = msg["text"].strip()
        cmd, _, arg = text.partition(" ")
        if cmd in ("/start", "/help"):
            self.send_text(
                "CreatorOS bot 👋\n\n"
                "/mode - show current mode\n"
                "/approval - every post waits for my OK\n"
                "/auto - publish automatically, just send me links\n"
                "/pause, /resume - stop or restart the daily schedule\n"
                "/write [type] [topic] - write a post now (e.g. /write future AI in farming)\n"
                "/status - recent posts")
        elif cmd == "/mode":
            self.send_text(self._mode_text(cfg))
        elif cmd in ("/auto", "/approval", "/pause", "/resume"):
            change = {
                "/auto": {"approval": {"required": False}},
                "/approval": {"approval": {"required": True}},
                "/pause": {"paused": True},
                "/resume": {"paused": False},
            }[cmd]
            from ..config import save_local_config
            new = save_local_config(change)
            cfg.clear()
            cfg.update(new)
            self.send_text(self._mode_text(cfg))
        elif cmd == "/write":
            import threading

            from ..modules.blog.angles import all_angles
            angle, _, topic = arg.strip().partition(" ")
            if angle and angle not in all_angles(cfg):
                angle, topic = "news", arg.strip()
            angle = angle or "news"
            self.send_text(f"⚡ Writing a '{html.escape(angle)}' post… (1-3 min)")

            def job():
                try:
                    pipeline.generate_post(cfg, angle, topic or None)
                except Exception as e:
                    self.send_text(f"⚠️ Writing failed: {html.escape(str(e))}")
            threading.Thread(target=job, daemon=True).start()
        elif cmd == "/status":
            rows = db.list_posts(8)
            self.send_text("\n".join(f"#{p['id']} [{p['status']}] {html.escape(p['title'] or '')}" for p in rows)
                           or "No posts yet.")
        elif self.awaiting_edit:
            post_id, self.awaiting_edit = self.awaiting_edit, None
            self.send_text(f"Revising #{post_id}…")
            pipeline.revise(cfg, post_id, text)


def find_chat_ids(token: str) -> list[tuple[str, str]]:
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20).json()
    if not r.get("ok"):
        raise RuntimeError(r.get("description"))
    found = {}
    for up in r["result"]:
        chat = (up.get("message") or up.get("callback_query", {}).get("message") or {}).get("chat")
        if chat:
            found[str(chat["id"])] = chat.get("username") or chat.get("first_name") or chat.get("title", "")
    return list(found.items())
