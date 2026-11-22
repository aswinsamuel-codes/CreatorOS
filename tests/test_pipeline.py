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
