"""Packages the Python engine into one executable for the desktop app.

    pip install -r requirements.txt pyinstaller
    python desktop/engine/build_engine.py            # → desktop/src-tauri/binaries/creatoros-engine-<target>

Tauri expects sidecar binaries named with the Rust target triple, e.g.
creatoros-engine-x86_64-pc-windows-msvc.exe. Pass --target to set it, otherwise it's detected
from `rustc -vV` (or guessed from the platform).
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "desktop" / "engine"
BIN_DIR = ROOT / "desktop" / "src-tauri" / "binaries"


def target_triple() -> str:
    try:
        out = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True).stdout
        return next(line.split(": ", 1)[1] for line in out.splitlines() if line.startswith("host: "))
    except Exception:
        machine = platform.machine().lower()
        arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
        if sys.platform == "win32":
            return f"{arch}-pc-windows-msvc"
        if sys.platform == "darwin":
            return f"{arch}-apple-darwin"
        return f"{arch}-unknown-linux-gnu"


def build(target: str) -> Path:
    sep = os.pathsep
    args = [
        str(ENGINE / "engine_main.py"),
        "--name", "creatoros-engine",
        "--onefile", "--noconfirm", "--clean",
        "--distpath", str(ENGINE / "dist"),
        "--workpath", str(ENGINE / "build"),
        "--specpath", str(ENGINE / "build"),
        "--paths", str(ROOT),
        f"--add-data={ROOT / 'config.yaml'}{sep}.",
        f"--add-data={ROOT / 'profile' / 'profile.example.yaml'}{sep}profile",
        f"--add-data={ROOT / 'creatoros' / 'dashboard' / 'static'}{sep}creatoros/dashboard/static",
        "--collect-submodules", "creatoros",
        "--collect-submodules", "uvicorn",
        "--collect-all", "apscheduler",
        "--copy-metadata", "apscheduler",
        "--collect-data", "tzdata",
        "--collect-data", "docx",
        "--collect-all", "pymupdf",
        "--copy-metadata", "anthropic",
        "--hidden-import", "tzlocal",
    ]
    if sys.platform == "win32":
        args.append("--noconsole")  # no black console window next to the app
    PyInstaller.__main__.run(args)

    exe = ".exe" if sys.platform == "win32" else ""
    built = ENGINE / "dist" / f"creatoros-engine{exe}"
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    dest = BIN_DIR / f"creatoros-engine-{target}{exe}"
    shutil.copy2(built, dest)
    print(f"Engine ready: {dest} ({dest.stat().st_size / 1e6:.0f} MB)")
    return dest


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--target", help="Rust target triple (default: detect)")
    a = p.parse_args()
    build(a.target or target_triple())
