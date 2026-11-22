"""Your documents (resume, portfolio, project write-ups, research...).

Uploaded files are converted to editable text. Every document marked "use in posts" is
given to the writer as background about the author.

Layout (all ignored by git):
    profile/documents/<name>.md          extracted text - this is what the writer reads (editable)
    profile/documents/originals/<file>   the file you uploaded
    profile/documents/index.json         {name: {original, enabled, uploaded_at}}
"""

import base64
import io
import json
import re
from datetime import datetime

from .config import PROFILE_DIR

DOCS_DIR = PROFILE_DIR / "documents"
ORIGINALS = DOCS_DIR / "originals"
INDEX = DOCS_DIR / "index.json"
ALLOWED = (".pdf", ".docx", ".txt", ".md")
MAX_BYTES = 10 * 1024 * 1024
PER_DOC_CHARS = 8000
TOTAL_CHARS = 20000


class DocumentError(ValueError):
    pass


def _index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {}


def _save_index(idx: dict) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")


def safe_name(filename: str) -> str:
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", filename)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-").lower()
    if not stem:
        raise DocumentError("Invalid file name")
    return stem[:60]


def extract_text(filename: str, data: bytes) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED:
        raise DocumentError(f"Unsupported file type. Use: {', '.join(ALLOWED)}")
    if ext in (".txt", ".md"):
        return data.decode("utf-8", errors="replace").strip()
    if ext == ".pdf":
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(data))
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as e:
            raise DocumentError(f"Could not read this PDF: {e}") from e
        if not text.strip():
            raise DocumentError("No text found in this PDF (is it a scanned image?). Paste the text instead.")
        return re.sub(r"[ \t]+\n", "\n", text).strip()
    from docx import Document  # .docx
    try:
        doc = Document(io.BytesIO(data))
    except Exception as e:
        raise DocumentError(f"Could not read this Word file: {e}") from e
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(parts).strip()


def add_document(filename: str, data: bytes) -> dict:
    if len(data) > MAX_BYTES:
        raise DocumentError("File is larger than 10 MB")
    text = extract_text(filename, data)
    name = safe_name(filename)
    ORIGINALS.mkdir(parents=True, exist_ok=True)
    ext = filename.rsplit(".", 1)[-1].lower()
    (ORIGINALS / f"{name}.{ext}").write_bytes(data)
    (DOCS_DIR / f"{name}.md").write_text(text, encoding="utf-8")
    idx = _index()
    idx[name] = {"original": f"{name}.{ext}", "enabled": True,
                 "uploaded_at": datetime.now().isoformat(timespec="seconds")}
    _save_index(idx)
    return {"name": name, "chars": len(text)}


def add_document_b64(filename: str, data_b64: str) -> dict:
    try:
        data = base64.b64decode(data_b64.split(",", 1)[-1], validate=True)
    except Exception as e:
        raise DocumentError("Upload was corrupted, please try again") from e
    return add_document(filename, data)


def create_text_document(name: str, text: str) -> dict:
    name = safe_name(name)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / f"{name}.md").write_text(text, encoding="utf-8")
    idx = _index()
    idx.setdefault(name, {"original": None, "enabled": True,
                          "uploaded_at": datetime.now().isoformat(timespec="seconds")})
    _save_index(idx)
    return {"name": name, "chars": len(text)}


def list_documents() -> list[dict]:
    idx = _index()
    out = []
    for name, meta in sorted(idx.items()):
        path = DOCS_DIR / f"{name}.md"
        if path.exists():
            out.append({"name": name, **meta, "chars": len(path.read_text(encoding="utf-8"))})
    return out


def _require(name: str) -> str:
    name = safe_name(name)
    if name not in _index():
        raise DocumentError(f"Document '{name}' not found")
    return name


def get_text(name: str) -> str:
    return (DOCS_DIR / f"{_require(name)}.md").read_text(encoding="utf-8")


def update_document(name: str, text: str | None = None, enabled: bool | None = None) -> None:
    name = _require(name)
    if text is not None:
        (DOCS_DIR / f"{name}.md").write_text(text, encoding="utf-8")
    if enabled is not None:
        idx = _index()
        idx[name]["enabled"] = bool(enabled)
        _save_index(idx)


def delete_document(name: str) -> None:
    name = _require(name)
    idx = _index()
    meta = idx.pop(name)
    (DOCS_DIR / f"{name}.md").unlink(missing_ok=True)
    if meta.get("original"):
        (ORIGINALS / meta["original"]).unlink(missing_ok=True)
    _save_index(idx)


def documents_prompt() -> str:
    """Text of enabled documents for the writer, capped so prompts stay a sensible size."""
    blocks, total = [], 0
    for doc in list_documents():
        if not doc.get("enabled"):
            continue
        text = (DOCS_DIR / f"{doc['name']}.md").read_text(encoding="utf-8").strip()
        if not text:
            continue
        text = text[:PER_DOC_CHARS]
        if total + len(text) > TOTAL_CHARS:
            text = text[: max(0, TOTAL_CHARS - total)]
        if not text:
            break
        blocks.append(f"--- {doc['name']} ---\n{text}")
        total += len(text)
    return "\n\n".join(blocks)
