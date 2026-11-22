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
    def complete(self, system, prompt, max_tokens=0):
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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
    print("All tests passed")
