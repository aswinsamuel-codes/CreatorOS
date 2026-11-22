"""End-to-end pipeline tests with a fake model: no API keys, no cost, no network.

Run:  python tests/test_pipeline.py      (or: pytest tests)
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from creatoros import config, db  # noqa: E402
from creatoros.modules.blog import pipeline, scout  # noqa: E402
from creatoros.publishers import markdown_file  # noqa: E402
from creatoros.settings import validate  # noqa: E402

POST_REPLY = (
    "TITLE: The Test Title\nSUBTITLE: A subtitle\nTAGS: AI, Technology, Future\n===\n"
    "# The Test Title\n\nHook line.\n\n## Section\n\nBody text.\n\n## Sources\n- [x](https://x)"
)


class FakeLLM:
    def complete(self, system, prompt, max_tokens=0, images=None):
        if "CAMPAIGN BRIEF" in prompt:
            import json
            import re as _re
            start, end = _re.search(r"Dates: (\S+) to (\S+)", prompt).groups()
            cal = [
                {"date": start, "time": "25:99", "format": "linkedin_post", "pillar": "Lessons", "topic": "My first AWS bill", "hook": "I paid $400", "cta": "Follow"},
                {"date": start, "time": "15:00", "format": "video_script", "pillar": "Tips", "topic": "3 cost tricks", "hook": "", "cta": "Save this"},
                {"date": end, "time": "10:00", "format": "blog_post", "pillar": "Guides", "topic": "Cutting AWS costs", "hook": "", "cta": "Book a call"},
                {"date": end, "time": "10:00", "format": "tiktok_dance", "pillar": "x", "topic": "invalid format"},
                {"date": "2001-01-01", "time": "10:00", "format": "linkedin_post", "pillar": "x", "topic": "out of range"},
            ]
            return json.dumps({"strategy": {"positioning": "The practical cloud cost person", "pillars": [{"name": "Lessons", "description": "d"}],
                                            "kpis": ["+500 followers"], "tips": ["Reply to comments"], "audience_insights": ["Bills scare founders"]},
                               "calendar": cal})
        if "THIS PIECE" in prompt or "Repurpose the source" in prompt:
            assert "YOUR ROLE" in system
            return '{"title": "Piece title", "subtitle": "Sub", "body": "Piece body text", "hashtags": ["#AWS", "Cloud"]}'
        if images and "VIDEO FACTS" in prompt:
            assert len(images) == 6
            return ('{"title": "Deploy FastAPI to AWS <fast>", "description": "Learn to deploy.", '
                    '"tags": ["fastapi", "aws deploy", "python"], '
                    '"chapters": [{"time": "0:00", "title": "Intro"}, {"time": "0:04", "title": "Too close"}, '
                    '{"time": "0:10", "title": "Setup"}, {"time": "0:20", "title": "Deploy"}], '
                    '"hashtags": ["#FastAPI", "AWS"], "linkedin_text": "I deployed FastAPI to AWS.", "thumbnail_frame": 2}')
        if images:  # folder inspection
            return ('{"type": "certificate", "title": "Cloud Practitioner", "issuer": "AWS", "date": "2026", '
                    '"skills": ["Cloud"], "summary": "AWS certificate", "alt_text": "AWS Cloud Practitioner certificate"}')
        if "AUTHOR'S INSTRUCTION" in prompt:
            assert "YOUR ROLE" in system
            return "TITLE: My certificates\nHASHTAGS: #AWS #Cloud\n===\nI earned new certificates (thanks AWS)!"
        if "Return JSON" in prompt:
            return '```json\n{"index": 1, "related": [], "topic": "Why this matters"}\n```'
        assert "AUTHOR PROFILE" in system
        return POST_REPLY


def setup():
    tmp = Path(tempfile.mkdtemp())
    db.DB_PATH, db.DATA_DIR = tmp / "test.db", tmp
    pipeline.BLOG_OUTPUT = markdown_file.BLOG_OUTPUT = tmp / "out"
    pipeline.get_llm = lambda cfg, role: FakeLLM()
    pipeline.research.fetch_text = lambda url: "article text"
    pipeline.notify.send_for_approval = lambda post: None
    pipeline.notify.send_published = lambda post: None
    scout.gather = lambda cfg: [
        {"title": "Story A", "url": "https://example.com/a", "source": "HN", "score": 1, "comments": 0, "key": "url:a"},
        {"title": "Story B", "url": "https://example.com/b", "source": "HN", "score": 2, "comments": 0, "key": "url:b"},
    ]
    db.init()
    cfg = config.load_config(str(config.ROOT / "config.yaml"))
    cfg["publish"]["targets"] = ["markdown"]
    return cfg


def test_approval_mode():
    cfg = setup()
    cfg["approval"]["required"] = True
    pid = pipeline.generate_post(cfg, "news")
    p = db.get_post(pid)
    assert p["status"] == "pending" and p["title"] == "The Test Title"
    assert not p["body"].startswith("# "), "duplicate H1 should be stripped"
    assert p["tags"] == ["AI", "Technology", "Future"]
    assert "url:b" in db.seen_keys()
    pipeline.publish_post(cfg, pid)
    assert db.get_post(pid)["status"] == "published"


def test_auto_mode():
    cfg = setup()
    cfg["approval"]["required"] = False
    pid = pipeline.generate_post(cfg, "business")
    p = db.get_post(pid)
    assert p["status"] == "published" and "markdown" in p["published"]


def test_settings_validation():
    cfg = setup()
    assert validate(cfg) == []
    bad = {**cfg, "timezone": "Mars/Base", "blog": {**cfg["blog"], "schedule": [{"time": "25:00", "angle": "nope"}]}}
    errors = validate(bad)
    assert len(errors) == 3, errors


def test_custom_angle():
    cfg = setup()
    cfg["blog"]["angles"] = {"tutorial": {"label": "Tutorial", "pick": "a tool", "write": "step by step"}}
    cfg["blog"]["schedule"] = [{"time": "10:00", "angle": "tutorial"}]
    assert validate(cfg) == []
    pid = pipeline.generate_post(cfg, "tutorial")
    assert db.get_post(pid)["angle"] == "tutorial"


def test_documents():
    import io

    from docx import Document

    from creatoros import documents, profile

    tmp = Path(tempfile.mkdtemp())
    documents.DOCS_DIR, documents.ORIGINALS, documents.INDEX = tmp, tmp / "originals", tmp / "index.json"

    buf = io.BytesIO()
    d = Document()
    d.add_paragraph("Aswin - AI engineer. Built a GPU cluster for local LLMs.")
    d.add_paragraph("Phone: +91 99999 00000")
    d.save(buf)
    r = documents.add_document("My Resume.docx", buf.getvalue())
    assert r["name"] == "my-resume"
    assert "GPU cluster" in documents.get_text("my-resume")
    assert (tmp / "originals" / "my-resume.docx").exists()

    documents.update_document("my-resume", text="Edited: built a GPU cluster.")
    assert "Edited" in profile.profile_prompt() and "Never include private details" in profile.profile_prompt()

    documents.update_document("my-resume", enabled=False)
    assert "Edited" not in profile.profile_prompt()

    documents.create_text_document("projects", "Project list")
    assert {x["name"] for x in documents.list_documents()} == {"my-resume", "projects"}

    try:
        documents.extract_text("virus.exe", b"x")
        raise AssertionError("exe should be rejected")
    except documents.DocumentError:
        pass

    documents.delete_document("my-resume")
    assert not (tmp / "originals" / "my-resume.docx").exists()


def _make_folder(n_images: int, with_pdf: bool = True) -> Path:
    import pymupdf
    from PIL import Image

    folder = Path(tempfile.mkdtemp())
    for i in range(n_images):
        Image.new("RGBA", (800, 600), (255, 200, 0, 255)).save(folder / f"cert_{i:02d}.png")
    if with_pdf:
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), "Certificate of Completion")
        doc.save(folder / "zz_cert.pdf")
    (folder / "notes.docx").write_text("ignored")  # unsupported file is skipped
    return folder


def _setup_folder_test():
    from creatoros.modules.social import folder as folder_mod
    from creatoros import publishers

    cfg = setup()
    folder_mod.MEDIA_DIR = Path(tempfile.mkdtemp())
    folder_mod.get_llm = lambda cfg, role: FakeLLM()
    folder_mod.notify.send_for_approval = lambda post: None
    sent = []
    publishers.PUBLISHERS["linkedin"] = lambda post, opts: sent.append(post) or f"https://linkedin/{post['id']}"
    return cfg, folder_mod, sent


def test_folder_series_and_schedule():
    from datetime import datetime, timedelta

    cfg, folder_mod, sent = _setup_folder_test()
    cfg["approval"]["required"] = True
    folder = _make_folder(2)
    ids = folder_mod.create_posts(cfg, str(folder), "one per day", ["linkedin"], mode="series", interval_hours=24)
    assert len(ids) == 3, ids  # 2 PNG + 1 PDF, docx skipped
    posts = [db.get_post(i) for i in ids]
    assert all(p["status"] == "pending" and p["kind"] == "social" for p in posts)
    assert all(Path(p["media"][0]["path"]).exists() for p in posts)
    assert posts[0]["media"][0]["alt"] == "AWS Cloud Practitioner certificate"
    assert "#AWS" in posts[0]["body"] and posts[0]["targets"] == ["linkedin"]

    assert pipeline.approve(cfg, ids[0]) == "published" and len(sent) == 1
    assert pipeline.approve(cfg, ids[1]) == "scheduled"           # due tomorrow
    pipeline.publish_due(cfg)
    assert db.get_post(ids[1])["status"] == "scheduled"
    db.update_post(ids[1], scheduled_at=(datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds"))
    pipeline.publish_due(cfg)
    assert db.get_post(ids[1])["status"] == "published" and len(sent) == 2


def test_folder_combined_splits_and_auto_mode():
    cfg, folder_mod, sent = _setup_folder_test()
    cfg["approval"]["required"] = False
    folder = _make_folder(22, with_pdf=False)
    ids = folder_mod.create_posts(cfg, str(folder), "all in one", ["linkedin"], mode="combined")
    assert [len(db.get_post(i)["media"]) for i in ids] == [20, 2]
    assert all(db.get_post(i)["status"] == "published" for i in ids) and len(sent) == 2


def test_linkedin_format_and_payload():
    from creatoros.publishers import linkedin

    assert linkedin.to_little_text("Hi (AWS) #Cloud_AI done") == "Hi \\(AWS\\) {hashtag|\\#|Cloud_AI} done"

    calls = {}

    class Resp:
        def __init__(self, status=201, data=None, headers=None):
            self.status_code, self._data, self.headers, self.text = status, data or {}, headers or {}, ""

        def json(self):
            return self._data

    def fake_post(url, **kw):
        if "initializeUpload" in url:
            n = calls.setdefault("uploads", 0) + 1
            calls["uploads"] = n
            return Resp(200, {"value": {"uploadUrl": "https://upload", "image": f"urn:li:image:{n}"}})
        calls["post"] = kw["json"]
        calls["headers"] = kw["headers"]
        return Resp(201, headers={"x-restli-id": "urn:li:share:99"})

    linkedin.requests.post = fake_post
    linkedin.requests.put = lambda url, **kw: Resp(201)
    linkedin.env = lambda k, d=None: {"LINKEDIN_ACCESS_TOKEN": "tok", "LINKEDIN_PERSON_URN": "urn:li:person:abc"}.get(k, d)

    img = Path(tempfile.mkdtemp()) / "a.jpg"
    img.write_bytes(b"x")
    post = {"id": 1, "kind": "social", "title": "t", "body": "Hello #AI",
            "media": [{"path": str(img), "alt": "one"}, {"path": str(img), "alt": "two"}]}
    url = linkedin.publish(post, {})
    assert url == "https://www.linkedin.com/feed/update/urn:li:share:99/"
    assert calls["post"]["author"] == "urn:li:person:abc"
    assert [i["id"] for i in calls["post"]["content"]["multiImage"]["images"]] == ["urn:li:image:1", "urn:li:image:2"]
    assert calls["headers"]["LinkedIn-Version"] and calls["headers"]["X-Restli-Protocol-Version"] == "2.0.0"


def _make_videos() -> Path:
    import subprocess

    folder = Path(tempfile.mkdtemp())
    for name, size, secs in (("tutorial.mp4", "640x360", 30), ("clip.mp4", "360x640", 6)):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=size={size}:rate=15",
                        "-f", "lavfi", "-i", "sine=frequency=440", "-t", str(secs), "-pix_fmt", "yuv420p",
                        "-shortest", str(folder / name)], check=True, capture_output=True)
    return folder


def test_video_posts():
    from creatoros.modules.video import posting, videoinfo
    from creatoros import publishers

    cfg = setup()
    cfg["approval"]["required"] = True
    posting.MEDIA_DIR = Path(tempfile.mkdtemp())
    posting.get_llm = lambda cfg, role: FakeLLM()
    posting.notify.send_for_approval = lambda post: None
    sent = []
    publishers.PUBLISHERS["youtube"] = lambda post, opts: sent.append(("yt", post["id"])) or "https://youtu.be/x"
    publishers.PUBLISHERS["linkedin"] = lambda post, opts: sent.append(("li", post["id"])) or "https://linkedin/x"

    folder = _make_videos()
    (folder / "readme.txt").write_text("not a video")
    files = videoinfo.scan(folder)
    assert [f.name for f in files] == ["clip.mp4", "tutorial.mp4"]
    info = videoinfo.probe(folder / "clip.mp4")
    assert info["vertical"] and 5 <= info["duration"] <= 7 and info["has_audio"]

    ids = posting.create_posts(cfg, str(folder), "tutorial", ["youtube", "linkedin"], privacy="unlisted",
                               interval_hours=12, transcribe=False)
    clip, tut = db.get_post(ids[0]), db.get_post(ids[1])
    assert clip["kind"] == "video" and clip["status"] == "pending"
    assert clip["title"].endswith("#Shorts") and "<" not in clip["title"]
    assert clip["meta"]["youtube"] == {"privacy": "unlisted", "category_id": "28", "short": True}
    assert not tut["meta"]["youtube"]["short"] and "#Shorts" not in tut["title"]
    assert tut["meta"]["chapters"] == [{"time": "0:00", "title": "Intro"}, {"time": "0:10", "title": "Setup"},
                                      {"time": "0:20", "title": "Deploy"}], tut["meta"]["chapters"]
    assert "0:10 Setup" in tut["body"] and "#FastAPI #AWS" in tut["body"]
    assert tut["meta"]["linkedin_text"].endswith("#FastAPI #AWS")
    assert Path(tut["media"][0]["thumb"]).name == "frame_02.jpg" and Path(tut["media"][0]["thumb"]).exists()
    assert tut["scheduled_at"] > clip["scheduled_at"]

    assert pipeline.approve(cfg, ids[0]) == "published"
    assert sent == [("yt", ids[0]), ("li", ids[0])]
    assert pipeline.approve(cfg, ids[1]) == "scheduled"


class _resp:
    def __init__(self, status=200, data=None, headers=None):
        self.status_code, self.headers, self.text, self._data = status, headers or {}, "", data or {}
        self.ok = status < 400

    def json(self):
        return self._data


def test_youtube_upload():
    from creatoros.publishers import youtube

    video = Path(tempfile.mkdtemp()) / "v.mp4"
    video.write_bytes(b"x" * 2500)
    thumb = video.with_suffix(".jpg")
    thumb.write_bytes(b"jpg")
    youtube.CHUNK = 1000
    youtube._token = lambda: "tok"
    calls = {"puts": []}

    def fake_post(url, **kw):
        if "thumbnails" in url:
            calls["thumb"] = True
            return _resp(200)
        calls["init"] = kw["json"]
        return _resp(200, headers={"Location": "https://upload/session"})

    def fake_put(url, data=None, headers=None, **kw):
        calls["puts"].append(headers["Content-Range"])
        done = headers["Content-Range"].endswith("2499/2500")
        return _resp(200 if done else 308, {"id": "abc123"})

    youtube.requests.post, youtube.requests.put = fake_post, fake_put
    post = {"title": "T", "body": "D", "tags": ["a"],
            "media": [{"path": str(video), "type": "video", "thumb": str(thumb)}],
            "meta": {"youtube": {"privacy": "unlisted", "category_id": "27", "short": False}}}
    assert youtube.publish(post, {}) == "https://youtu.be/abc123"
    assert calls["puts"] == ["bytes 0-999/2500", "bytes 1000-1999/2500", "bytes 2000-2499/2500"]
    assert calls["init"]["status"]["privacyStatus"] == "unlisted" and calls["init"]["snippet"]["categoryId"] == "27"
    assert calls.get("thumb")


def test_linkedin_video_upload():
    from creatoros.publishers import linkedin

    video = Path(tempfile.mkdtemp()) / "v.mp4"
    video.write_bytes(b"y" * 300)
    calls = {"parts": []}

    def fake_post(url, **kw):
        if "initializeUpload" in url:
            return _resp(200, {"value": {"video": "urn:li:video:1", "uploadToken": "t", "uploadInstructions": [
                {"uploadUrl": "https://u/1", "firstByte": 0, "lastByte": 199},
                {"uploadUrl": "https://u/2", "firstByte": 200, "lastByte": 299}]}})
        if "finalizeUpload" in url:
            calls["final"] = kw["json"]
            return _resp(200)
        calls["post"] = kw["json"]
        return _resp(201, headers={"x-restli-id": "urn:li:share:7"})

    def fake_put(url, data=None, **kw):
        calls["parts"].append(len(data))
        return _resp(200, headers={"ETag": f'"etag{len(calls["parts"])}"'})

    linkedin.requests.post, linkedin.requests.put = fake_post, fake_put
    linkedin.requests.get = lambda url, **kw: _resp(200, {"status": "AVAILABLE"})
    linkedin.env = lambda k, d=None: {"LINKEDIN_ACCESS_TOKEN": "tok", "LINKEDIN_PERSON_URN": "urn:li:person:abc"}.get(k, d)
    post = {"id": 2, "kind": "video", "title": "Demo", "body": "yt desc",
            "media": [{"path": str(video), "type": "video"}], "meta": {"linkedin_text": "My demo #AI"}}
    assert linkedin.publish(post, {}).endswith("urn:li:share:7/")
    assert calls["parts"] == [200, 100]
    assert calls["final"]["finalizeUploadRequest"]["uploadedPartIds"] == ["etag1", "etag2"]
    assert calls["post"]["content"]["media"]["id"] == "urn:li:video:1"
    assert calls["post"]["commentary"].startswith("My demo")


def test_custom_webhook_platform():
    import base64 as b64

    from creatoros import connections, publishers
    from creatoros.publishers import webhook

    connections.STORE = Path(tempfile.mkdtemp()) / "connections.json"
    try:
        connections.save_custom(None, {"name": "Insta", "url": "ftp://bad"})
        raise AssertionError("bad URL should be rejected")
    except ValueError:
        pass
    cid = connections.save_custom(None, {"name": "Instagram via Zapier", "url": "https://hooks.example/abc",
                                         "auth_header": "X-Key", "api_key": "secret"})
    assert cid == "instagram-via-zapier"
    assert publishers.is_target(f"custom:{cid}") and not publishers.is_target("custom:nope")
    cfg = setup()
    cfg["publish"]["targets"] = ["markdown", f"custom:{cid}"]
    assert validate(cfg) == []
    connections.save_custom(cid, {"name": "Instagram via Zapier", "url": "https://hooks.example/abc"})
    assert connections.list_custom()[cid]["api_key"] == "secret", "empty key field keeps the saved key"

    img = Path(tempfile.mkdtemp()) / "a.jpg"
    img.write_bytes(b"IMG")
    sent = {}

    def fake_request(method, url, json=None, headers=None, timeout=None):
        sent.update(method=method, url=url, json=json, headers=headers)
        return _resp(200, {"url": "https://instagram.com/p/xyz"})

    webhook.requests.request = fake_request
    post = {"id": 5, "kind": "social", "title": "Certs", "body": "My certs #AWS", "tags": ["AWS"],
            "media": [{"path": str(img), "alt": "cert"}], "published": {}}
    assert publishers.publish_to(f"custom:{cid}", post, cfg) == "https://instagram.com/p/xyz"
    assert sent["headers"]["X-Key"] == "secret" and sent["json"]["text"] == "My certs #AWS"
    assert b64.b64decode(sent["json"]["media"][0]["data_base64"]) == b"IMG"
    connections.delete_custom(cid)
    assert not publishers.is_target(f"custom:{cid}")


def test_marketing_campaign():
    from datetime import date, timedelta

    from creatoros.modules.marketing import content, planner

    cfg = setup()
    cfg["approval"]["required"] = True
    planner.get_llm = content.get_llm = lambda cfg, role: FakeLLM()
    content.notify.send_for_approval = lambda post: None
    start = (date.today() + timedelta(days=1)).isoformat()
    cid = db.create_campaign("Cloud costs", {
        "goal": "Get freelance leads", "audience": "founders", "formats": ["linkedin_post", "video_script", "blog_post"],
        "targets": {}, "start": start, "weeks": 1, "per_week": 3, "role": "marketing_strategist"})
    assert planner.plan_campaign(cfg, cid) == 3  # invalid format and out-of-range date dropped
    camp = db.get_campaign(cid)
    assert camp["status"] == "active" and camp["strategy"]["positioning"]
    cal = db.list_calendar(cid)
    by_fmt = {i["format"]: i for i in cal}
    assert by_fmt["linkedin_post"]["due"] == f"{start}T09:00:00"  # bad time → best time
    assert by_fmt["linkedin_post"]["targets"] == ["linkedin"]
    assert by_fmt["video_script"]["targets"] == []
    assert by_fmt["blog_post"]["targets"] == ["markdown"]  # blog → blog targets from settings

    cfg["paused"] = True
    assert content.generate_due(cfg, hours=24 * 9) == []
    cfg["paused"] = False
    db.update_campaign(cid, status="paused")
    assert content.generate_due(cfg, hours=24 * 9) == []
    db.update_campaign(cid, status="active")
    ids = content.generate_due(cfg, hours=24 * 9)
    assert len(ids) == 3 and all(i["status"] == "drafted" and i["post_id"] for i in db.list_calendar(cid))

    posts = {db.get_post(i)["angle"]: db.get_post(i) for i in ids}
    li, script, blog = posts["linkedin_post"], posts["video_script"], posts["blog_post"]
    assert li["kind"] == "social" and li["status"] == "pending" and "#AWS #Cloud" in li["body"]
    assert li["meta"]["campaign"] == "Cloud costs" and li["scheduled_at"] == f"{start}T09:00:00"
    assert script["kind"] == "draft" and script["targets"] == []
    assert blog["kind"] == "blog" and blog["targets"] == ["markdown"]
    assert pipeline.approve(cfg, script["id"]) == "ready"
    assert pipeline.approve(cfg, li["id"]) == "scheduled"

    new = content.repurpose(cfg, blog["id"], ["x_thread", "linkedin_post"])
    thread, li2 = db.get_post(new[0]), db.get_post(new[1])
    assert thread["kind"] == "draft", "thread with no connected platform becomes a draft"
    assert li2["kind"] == "social" and li2["targets"] == ["linkedin"] and li2["meta"]["repurposed_from"] == blog["id"]
    db.delete_campaign(cid)
    assert db.get_campaign(cid) is None and db.list_calendar(cid) == []


def test_ai_providers_and_usage():
    from datetime import datetime

    from creatoros import llm

    setup()
    sent = []

    def post_with_text(url, json=None, headers=None, timeout=None):
        sent.append(dict(json))
        if "max_tokens" in json:  # pretend this server only accepts max_completion_tokens
            r = _resp(400)
            r.text = "Unsupported parameter: 'max_tokens'"
            return r
        return _resp(200, {"choices": [{"message": {"content": "<think>x</think>Hello"}}],
                           "usage": {"prompt_tokens": 120, "completion_tokens": 30}})

    llm.requests.post = post_with_text
    gem = llm.OpenAICompatibleLLM("gemini-x", "https://generativelanguage.googleapis.com/v1beta/openai", "k", provider="gemini")
    assert gem.complete("s", "p", max_tokens=50) == "Hello"
    assert "max_tokens" in sent[0] and "max_completion_tokens" in sent[1], "retries with max_completion_tokens"
    oa = llm.OpenAICompatibleLLM("gpt-x", "https://api.openai.com/v1", "k", provider="openai")
    oa.complete("s", "p", max_tokens=50)
    assert "max_completion_tokens" in sent[-1] and "max_tokens" not in sent[-1]

    month = db.usage_summary(datetime.now().replace(day=1).isoformat()[:10])
    assert month["gemini"] == {"input": 120, "output": 30, "calls": 1} and month["openai"]["calls"] == 1

    assert "no credits" in llm.friendly_http_error("https://api.openai.com/v1", 429, '{"code":"insufficient_quota"}')
    assert "rejected the API key" in llm.friendly_http_error("https://generativelanguage.googleapis.com", 400, "API key not valid")
    assert "no API credits" in llm.friendly_claude_error(400, "Your credit balance is too low")

    llm.requests.get = lambda url, headers=None, timeout=None: _resp(200, {"data": [
        {"id": "models/gemini-9-pro"}, {"id": "models/gemini-9-flash"}, {"id": "models/text-embedding-004"}, {"id": "models/imagen-4"}]})
    cfg = setup()
    cfg["providers"]["gemini"]["api_key_env"] = ""
    models = llm.list_models(cfg, "gemini")
    assert models == ["gemini-9-pro", "gemini-9-flash"] and llm.cheapest(models) == "gemini-9-flash"


def test_personas():
    from creatoros.personas import persona_prompt

    cfg = setup()
    cfg["persona"] = {"role": "marketing_strategist", "custom": "Write for students"}
    text = persona_prompt(cfg)
    assert "strategist" in text and "Write for students" in text
    assert "patient teacher" in persona_prompt(cfg, role="educator", custom="")
    cfg["persona"] = {"role": "custom", "custom": ""}
    assert any("Custom agent role" in e for e in validate(cfg))
    cfg["persona"] = {"role": "custom", "custom": "Be a gaming streamer"}
    assert validate(cfg) == [] and "gaming streamer" in persona_prompt(cfg)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
    print("All tests passed")
