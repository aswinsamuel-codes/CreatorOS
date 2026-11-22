"""Look inside a video: duration, size, orientation, sample frames and (optionally) a transcript."""

import base64
import json
import shutil
import subprocess
from pathlib import Path

from ...config import log

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}


def _run(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg is not installed or not on PATH (https://ffmpeg.org/download.html)")


def scan(path: str | Path) -> list[Path]:
    """A single video file, or every video in a folder."""
    p = Path(path).expanduser()
    if p.is_file():
        if p.suffix.lower() not in VIDEO_EXT:
            raise FileNotFoundError(f"Not a supported video: {p.name} ({', '.join(sorted(VIDEO_EXT))})")
        return [p]
    if not p.is_dir():
        raise FileNotFoundError(f"File or folder not found: {p}")
    files = [f for f in sorted(p.iterdir()) if f.is_file() and f.suffix.lower() in VIDEO_EXT]
    if not files:
        raise FileNotFoundError(f"No videos in {p} (supported: {', '.join(sorted(VIDEO_EXT))})")
    return files


def probe(path: Path) -> dict:
    require_ffmpeg()
    r = _run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    if r.returncode != 0:
        raise RuntimeError(f"Could not read video {path.name}: {r.stderr.strip()[:200]}")
    data = json.loads(r.stdout)
    video = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    if not video:
        raise RuntimeError(f"{path.name} has no video stream")
    width, height = int(video.get("width", 0)), int(video.get("height", 0))
    rotation = 0
    for sd in video.get("side_data_list", []) or []:
        rotation = abs(int(sd.get("rotation", 0) or 0))
    if rotation in (90, 270):
        width, height = height, width
    duration = float(data["format"].get("duration") or video.get("duration") or 0)
    return {
        "duration": round(duration, 2), "width": width, "height": height,
        "vertical": height > width, "size_bytes": int(data["format"].get("size") or path.stat().st_size),
        "has_audio": any(s.get("codec_type") == "audio" for s in data["streams"]),
    }


def extract_frames(path: Path, duration: float, out_dir: Path, count: int = 6) -> list[Path]:
    """Evenly spaced JPEG frames (also used as thumbnail candidates)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(count):
        t = duration * (i + 0.5) / count if duration > 0 else 0
        out = out_dir / f"frame_{i:02d}.jpg"
        r = _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                  "-vf", "scale='min(1280,iw)':-2", "-q:v", "3", str(out)], timeout=120)
        if r.returncode == 0 and out.exists():
            frames.append(out)
    if not frames:
        raise RuntimeError(f"Could not extract frames from {path.name}")
    return frames


def frame_b64(frame: Path) -> tuple[str, str]:
    return "image/jpeg", base64.b64encode(frame.read_bytes()).decode()


def transcribe(path: Path, model_size: str = "base") -> list[dict] | None:
    """Speech to text with faster-whisper (optional, runs locally for free).
    Returns [{"start": seconds, "text": "..."}] or None if unavailable."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        log.info("faster-whisper not installed - skipping transcript (pip install faster-whisper)")
        return None
    try:
        model = WhisperModel(model_size, device="auto", compute_type="int8")
        segments, _ = model.transcribe(str(path), vad_filter=True)
        return [{"start": round(s.start, 1), "text": s.text.strip()} for s in segments if s.text.strip()]
    except Exception as e:
        log.warning("Transcription failed for %s: %s", path.name, e)
        return None


def fmt_time(seconds: float) -> str:
    s = int(seconds)
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def transcript_text(segments: list[dict] | None, max_chars: int = 15000) -> str:
    if not segments:
        return ""
    text = "\n".join(f"[{fmt_time(s['start'])}] {s['text']}" for s in segments)
    return text[:max_chars]
