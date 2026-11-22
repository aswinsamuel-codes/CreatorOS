"""CreatorOS command line.

    python -m creatoros check                 # verify keys, Medium, Telegram, FFmpeg
    python -m creatoros scout                 # show today's candidate stories
    python -m creatoros write --angle news    # write one post now (optionally --topic "...")
    python -m creatoros folder D:\Certs -i "share all in one post" --to linkedin
    python -m creatoros video D:\Videos\demo.mp4 -i "FastAPI tutorial" --to youtube,linkedin
    python -m creatoros list                  # list posts
    python -m creatoros publish 3             # publish post #3
    python -m creatoros telegram-chat-id      # find your Telegram chat id
    python -m creatoros run                   # 24/7 mode: schedule + Telegram bot + dashboard
"""

import argparse
import shutil
import sys
import threading

from . import db
from .config import env, load_config, log, setup_logging


def cmd_check(cfg, _):
    ok = True

    def line(good, label, detail=""):
        nonlocal ok
        ok &= good
        print(f"  {'OK ' if good else 'XX '} {label}{' - ' + detail if detail else ''}")

    print("CreatorOS check")
    for role in ("writer", "scout"):
        spec = cfg["models"][role]
        prov = cfg["providers"][spec["provider"]]
        key_env = prov.get("api_key_env")
        need_key = bool(key_env)
        line(not need_key or bool(env(key_env)), f"{role} model: {spec['provider']}/{spec['model']}",
             f"{key_env} missing in .env" if need_key and not env(key_env) else "")
    if "medium" in cfg["publish"]["targets"]:
        if env("MEDIUM_TOKEN"):
            try:
                from .publishers import medium
                me = medium.me()
                line(True, "Medium", f"connected as @{me.get('username')}")
            except Exception as e:
                line(False, "Medium", str(e))
        else:
            line(False, "Medium", "MEDIUM_TOKEN missing in .env")
    if env("TELEGRAM_BOT_TOKEN") and env("TELEGRAM_CHAT_ID"):
        try:
            from .notify.telegram import Telegram
            b = Telegram.from_env()
            bot = b.api("getMe")
            line(True, "Telegram", f"bot @{bot['username']}")
        except Exception as e:
            line(False, "Telegram", str(e))
    else:
        line(False, "Telegram", "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set (posts will wait in the dashboard)")
    line(bool(shutil.which("ffmpeg")), "FFmpeg (video module)", "" if shutil.which("ffmpeg") else "not on PATH")
    return 0 if ok else 1


def cmd_scout(cfg, _):
    from .modules.blog import scout
    for c in scout.gather(cfg)[:40]:
        print(f"[{c['source']:<16}] {c['score']:>5}  {c['title']}")


def cmd_write(cfg, args):
    from .modules.blog import pipeline
    post_id = pipeline.generate_post(cfg, args.angle, args.topic, notify_user=not args.no_notify)
    p = db.get_post(post_id)
    print(f"\nPost #{post_id} [{p['status']}]: {p['title']}")
    print(f"Saved to: {pipeline.save_markdown(p)}")


def cmd_folder(cfg, args):
    from .modules.social import folder
    ids = folder.create_posts(cfg, args.path, args.instructions or "", args.to.split(","), args.mode,
                              args.interval, notify_user=not args.no_notify, role=args.role)
    for pid in ids:
        p = db.get_post(pid)
        print(f"\nPost #{pid} [{p['status']}] -> {', '.join(p['targets'])} at {p['scheduled_at']}\n{p['body']}\n")


def cmd_video(cfg, args):
    from .modules.video import posting
    ids = posting.create_posts(cfg, args.path, args.instructions or "", args.to.split(","), args.privacy,
                               args.category, args.interval, transcribe=not args.no_transcript,
                               notify_user=not args.no_notify, role=args.role)
    for pid in ids:
        p = db.get_post(pid)
        print(f"\nPost #{pid} [{p['status']}] -> {', '.join(p['targets'])} at {p['scheduled_at']}\n"
              f"TITLE: {p['title']}\nTAGS: {', '.join(p['tags'])}\n\n{p['body']}\n")


def cmd_list(cfg, _):
    for p in db.list_posts(30):
        print(f"#{p['id']:<4} {p['status']:<10} {p['angle']:<9} {p['title']}")


def cmd_publish(cfg, args):
    from .modules.blog import pipeline
    print(pipeline.publish_post(cfg, args.id))


def cmd_chat_id(cfg, _):
    from .notify.telegram import find_chat_ids
    token = env("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN in .env first.")
        return 1
    chats = find_chat_ids(token)
    if not chats:
        print("No messages found. Send any message to your bot on Telegram, then run this again.")
    for cid, name in chats:
        print(f"TELEGRAM_CHAT_ID={cid}    ({name})")


def cmd_run(cfg, args):
    import uvicorn

    from . import notify, scheduler
    from .dashboard.app import create_app

    sched = scheduler.start(cfg)
    bot = notify.bot()
    if bot:
        threading.Thread(target=bot.poll_forever, args=(cfg,), daemon=True).start()
        notify.send_text("🟢 CreatorOS is running.")
    else:
        log.info("Telegram not configured - approve posts in the dashboard")
    d = cfg.get("dashboard", {})
    host, port = d.get("host", "127.0.0.1"), d.get("port", 8787)
    url = f"http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}"
    log.info("Dashboard: %s", url)
    if not getattr(args, "no_browser", False):
        import webbrowser
        threading.Timer(2.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(cfg, sched), host=host, port=port, log_level="warning")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="creatoros", description="CreatorOS - AI content studio")
    parser.add_argument("--config", help="path to config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("scout")
    w = sub.add_parser("write")
    w.add_argument("--angle", default="news")
    w.add_argument("--topic")
    w.add_argument("--no-notify", action="store_true")
    fo = sub.add_parser("folder", help="turn a folder of images/PDFs into social posts")
    fo.add_argument("path")
    fo.add_argument("--instructions", "-i", default="")
    fo.add_argument("--to", default="linkedin", help="comma-separated targets")
    fo.add_argument("--mode", choices=["combined", "series"], default="combined")
    fo.add_argument("--interval", type=float, default=24, help="hours between series posts")
    fo.add_argument("--role", help="agent role, e.g. personal_brand")
    fo.add_argument("--no-notify", action="store_true")
    vi = sub.add_parser("video", help="write YouTube/LinkedIn metadata for a video or folder of videos")
    vi.add_argument("path")
    vi.add_argument("--instructions", "-i", default="")
    vi.add_argument("--to", default="youtube", help="comma-separated: youtube,linkedin")
    vi.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    vi.add_argument("--category", default="28", help="YouTube category id (28 = Science & Technology)")
    vi.add_argument("--interval", type=float, default=24, help="hours between videos")
    vi.add_argument("--role")
    vi.add_argument("--no-transcript", action="store_true")
    vi.add_argument("--no-notify", action="store_true")
    sub.add_parser("list")
    p = sub.add_parser("publish")
    p.add_argument("id", type=int)
    sub.add_parser("telegram-chat-id")
    r = sub.add_parser("run")
    r.add_argument("--no-browser", action="store_true", help="don't open the dashboard in a browser")
    args = parser.parse_args(argv)

    setup_logging()
    cfg = load_config(args.config)
    db.init()
    handlers = {"check": cmd_check, "scout": cmd_scout, "write": cmd_write, "folder": cmd_folder, "video": cmd_video,
                "list": cmd_list,
                "publish": cmd_publish, "telegram-chat-id": cmd_chat_id, "run": cmd_run}
    try:
        return handlers[args.cmd](cfg, args) or 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        log.error("%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
