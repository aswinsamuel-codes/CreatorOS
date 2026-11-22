# CreatorOS desktop app

A real installable app for Windows, macOS and Linux, built with **Rust + [Tauri](https://tauri.app)**.
No Python, no terminal, no `.bat` file needed.

## Download

Open the [latest release](https://github.com/aswinsamuel-codes/CreatorOS/releases/latest) and pick:

| Your computer | File |
|---|---|
| Windows | `CreatorOS_<version>_x64-setup.exe` (or the `.msi`) |
| macOS (Apple Silicon) | `CreatorOS_<version>_aarch64.dmg` |
| Linux | `.AppImage`, `.deb` or `.rpm` |

Every version tag (`v0.6.0`, `v0.7.0`…) builds new installers automatically and attaches them to
that release, so the app version always matches the release.

> The app isn't code-signed yet. Windows: "Windows protected your PC" → **More info** → **Run anyway**.
> macOS: right-click the app → **Open** the first time.

## What it does

- **Starts the CreatorOS engine for you** (bundled inside the app) and opens the dashboard in its own window.
- **Tray icon** (next to the clock): click to open; right-click for *Open in browser*,
  *Start at login* and *Quit CreatorOS*.
- **Closing the window keeps CreatorOS running** in the tray, so scheduled posts still go out.
  Use *Quit CreatorOS* to stop it.
- **Start at login** option, so your daily schedule runs without you opening anything.
- **One copy at a time:** opening it again just brings the window to the front.
- **Works with an engine you already run** (e.g. `start_creatoros.bat` or Docker on port 8787):
  the app uses it and won't stop it when you quit.

## Where your data lives

The app keeps your data in your user app-data folder, separate from the app, so updates never touch it:

| OS | Folder |
|---|---|
| Windows | `%APPDATA%\io.github.aswinsamuel.creatoros` |
| macOS | `~/Library/Application Support/io.github.aswinsamuel.creatoros` |
| Linux | `~/.local/share/io.github.aswinsamuel.creatoros` |

Inside: `data/` (database, connections, settings), `profile/`, `workspace/`, `logs/`.

## How it's built

```
desktop/
  src-tauri/          Rust app: window, tray, autostart, single instance, engine lifecycle
    src/main.rs
    tauri.conf.json
    icons/            generated from assets/logo-1024.png (npm run icons)
    binaries/         the packaged engine (built in CI, not committed)
  splash/             start-up screen shown while the engine boots
  engine/             PyInstaller entry point + build script for the engine
```

- The Python engine is packaged into one executable with **PyInstaller** and shipped as a Tauri
  **sidecar** (`binaries/creatoros-engine-<target-triple>`).
- The Rust side starts the sidecar with `CREATOROS_HOME` set to the app-data folder, keeps its
  output pipe drained, and on quit asks the engine to stop (`POST /api/shutdown`, local only)
  before killing it.
- CI: every push compiles and lints the Rust app (`cargo clippy`); version tags build installers
  on Windows, macOS and Linux runners, smoke-test the packaged engine, and attach the installers to
  the release (`.github/workflows/desktop.yml`).

## Building it yourself

Requirements: Rust (rustup), Node.js 20+, Python 3.11, and on Linux the WebKitGTK packages.

```bash
pip install -r requirements.txt pyinstaller
python desktop/engine/build_engine.py      # package the engine
cd desktop
npm install
npm run dev                                 # run the app in development
npm run build                               # make installers in src-tauri/target/release/bundle
```

## Notes

- Video features need FFmpeg installed on the computer (it isn't bundled yet).
- The logo is drawn by `assets/make_logo.py`; regenerate icons with `npm run icons` in `desktop/`.
