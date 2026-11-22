# Changelog

All notable changes are listed here. The project follows [Semantic Versioning](https://semver.org).

## [Unreleased]

### Added
- **Desktop app (Rust + Tauri)** for Windows, macOS and Linux: bundled engine (PyInstaller sidecar),
  splash screen, tray icon (open, open in browser, start at login, quit), close-to-tray, single
  instance, data in the user app-data folder, clean engine shutdown.
- **Logo** (neo-brutalist C + spark): app icons, dashboard header, favicon, README.
- **Opening animation**: the tile drops in, the C draws itself, the spark pops, the wordmark
  stamps in, then the app zooms into the dashboard (respects "reduce motion").
- CI compiles and lints the Rust app on every push; version tags build installers on all three
  platforms, smoke-test the packaged engine and attach installers to the GitHub Release.
- `CREATOROS_HOME` (data folder separate from the app) and `POST /api/shutdown` (local only).

## [0.5.0] - 2026-11-22

### Added
- **Docker support**: multi-stage `Dockerfile` (slim runtime, non-root user, health check, FFmpeg),
  `docker-compose.yml` with data volumes, optional local Ollama service (`--profile local-ai`),
  `.dockerignore` that keeps secrets and personal data out of the image.
  `CREATOROS_HOST`, `CREATOROS_PORT` and `CREATOROS_LOCAL_CONFIG` environment overrides.
- **GitHub Actions**: CI runs the tests, builds the image and smoke-tests the container on every
  push; version tags publish multi-arch images (amd64/arm64) to GitHub Container Registry.
- **📋 Copy for Medium**: copies the formatted post and opens Medium's editor (for accounts without
  integration tokens), plus "Mark as posted on Medium".
- **Google Gemini** and **OpenAI** tiles on the Connections tab, with guided steps and a Test
  that checks the key really has quota.
- **Use this AI**: choose a model from your account and use it for writing and/or picking
  stories, straight from the tile (no settings files).
- **🗑️ Remove** on every tile: deletes saved keys, logins and matching `.env` lines.
- **Token usage meters**: every AI request is counted; each AI tile shows a 0-100% bar of a
  monthly token budget (editable) plus input/output tokens, requests and today's usage.

- **Automatic retries and backup models**: temporary errors (server busy, dropped connection,
  timeout) are retried; if a model stays overloaded, CreatorOS switches to the provider's
  `fallback_models` (Gemini: `gemini-2.5-flash`, then `gemini-flash-lite-latest`).
- Model dropdowns hide non-text models (music, image, robotics, live voice) and list stable
  "latest" models first.

### Fixed
- Claude Test now catches accounts without API credits; plain-language errors for credits,
  quota, rate limits, bad keys and unknown models (Claude, OpenAI, Gemini).
- OpenAI's newer models get `max_completion_tokens` (they reject `max_tokens`).
- The cheap-model picker no longer mistakes "gemini" for a "mini" model.
- Reddit timeouts no longer slow down every run.

## [0.4.0] - 2026-11-22

### Added
- **Marketing agent**: campaigns from a goal, audience, offer and links → strategy (positioning,
  pillars, audience insights, KPIs, tips) and a dated content calendar at default best times.
  Calendar items can be rescheduled, edited, skipped or written now; active campaigns write each
  piece `marketing.lead_hours` before it's due (job every 30 minutes).
- Formats: LinkedIn post, X thread, Instagram caption, blog article, short-video script,
  newsletter. Formats with nowhere to publish become **drafts** (Copy / Mark ready).
- **♻️ Repurpose** any post into other formats.
- Marketing tab in the dashboard; campaign and format badges on posts.

- `python -m creatoros run` (and `start_creatoros.bat`) open the dashboard in your browser
  automatically (`--no-browser` to turn off).

### Fixed
- Pop-up windows now also work outside the Connections tab.
- When the CreatorOS engine isn't running (or the page was opened as a file), the dashboard shows
  a clear red banner with how to start it, instead of silent errors and empty pages.
- Quieter console output (scheduler and HTTP library logs only show warnings).

## [0.3.0] - 2026-11-22

### Added
- **Folder → post**: point the agent at a folder of certificates, badges, screenshots or
  photos (JPG, PNG, WEBP, PDF). A vision model reads each file and the writer creates
  LinkedIn posts, as one multi-image post (split above 20) or a scheduled series.
  Dashboard tab with example instructions, plus `python -m creatoros folder`.
- **LinkedIn publisher** using the official API with "Connect with LinkedIn" (OAuth):
  text, single-image and multi-image posts, alt text, hashtags.
- **Connections tab**: OAuth status, redirect URL, and API keys saved locally
  (`data/connections.json`); `.env` still takes priority.
- **Agent roles**: tech blogger, marketing strategist, developer advocate, content creator,
  personal-brand coach, startup founder, teacher, or custom; per-job override for folder posts.
- Scheduled posts: approving a future post marks it `scheduled`; published automatically
  when due. "Publish now" in the dashboard.
- Telegram previews include the post images.
- Image input for models (Claude and OpenAI-compatible vision models).
- **Video → post**: inspect a video or folder (ffprobe, sampled frames, optional local
  faster-whisper transcript); the writer produces YouTube title, description, tags, chapters,
  thumbnail choice and a LinkedIn caption. Vertical clips up to 3 minutes become Shorts.
  Dashboard tab and `python -m creatoros video`.
- **YouTube publisher**: Google OAuth with refresh token, resumable chunked upload with retries,
  custom thumbnail.
- **LinkedIn video**: multi-part Videos API upload, finalize and processing wait.
- **Connections redesign** for non-developers: platform tiles with step-by-step setup windows,
  Test buttons, Telegram "Find my chat ID", copy-able redirect URLs.
- **＋ Add a platform**: custom platforms via any webhook/API URL (Zapier, Make, n8n…), with
  optional auth header, media as base64, and "Send test".

### Changed
- `start_creatoros.bat` uses the project's `.venv` when present.

## [0.2.0] - 2026-11-22

### Added
- **Documents** in My profile: upload a resume, portfolio or project write-ups (PDF, Word,
  TXT, MD) or create text documents. They're converted to editable text, can be switched
  on or off per document, and are given to the writer as background about the author, with
  rules against leaking private details. Documents are ignored by git.

## [0.1.0] - 2026-11-22

First public release.

### Added
- Blog pipeline: scout (Hacker News, Reddit, RSS) → editor picks a story → research →
  writer → optional review pass.
- Post types: `news`, `future`, `business`, `fun`, `personal` (from your own notes), plus
  custom types in config.
- Personal profile (`profile/profile.yaml`) and notes folder used in every post.
- Model layer: Claude (Anthropic SDK) and any OpenAI-compatible server (Ollama, LM Studio,
  vLLM, OpenAI, Gemini), with separate writer and scout roles.
- **Approval mode** and **Auto mode**, plus pause/resume.
- Telegram bot: Publish / Edit / Skip / Full text buttons, and `/auto`, `/approval`,
  `/pause`, `/resume`, `/write`, `/status`, `/mode` commands.
- Publishers: Medium, dev.to, Markdown files.
- Neo-brutalist local dashboard: posts, write now, profile and notes, full settings
  editor (schedule, timezone, models, providers, sources, publishing), advanced YAML.
- Fully customisable schedule (times, days, enable/disable, timezone) that reloads live.
- `config.local.yaml` overrides with validation; secrets kept in `.env`.
- CLI: `check`, `scout`, `write`, `list`, `publish`, `telegram-chat-id`, `run`.
- Video module folders and plan (implementation planned for v0.3).
