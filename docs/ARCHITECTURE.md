# Architecture

CreatorOS is a single Python process that runs four things together:

```
                    ┌──────────────────────────────────────────────┐
                    │              python -m creatoros run          │
                    │                                              │
  config.yaml ─────▶│  Scheduler (APScheduler)                     │
  config.local.yaml │    └─ every slot ─▶ Blog pipeline            │
  .env              │                                              │
  profile/          │  Telegram bot (long polling thread)          │
                    │    └─ buttons/commands ─▶ pipeline / settings│
                    │                                              │
                    │  Dashboard (FastAPI + one HTML page)         │
                    │    └─ REST API ─▶ pipeline / settings        │
                    │                                              │
                    │  SQLite (data/creatoros.db)                  │
                    └──────────────────────────────────────────────┘
```

All three entry points (scheduler, Telegram, dashboard) share **one config dict**. When
settings change, that dict is updated in place and the scheduler reloads its slots, so
changes apply without a restart (except the dashboard's host/port).

## Blog pipeline

`creatoros/modules/blog/pipeline.py`

| Step | Module | What happens |
|---|---|---|
| 1. Scout | `scout.py` | Pulls stories from Hacker News (Firebase API), Reddit (`top.json`) and RSS feeds. Removes duplicates and anything already used (`seen` table). |
| 2. Pick | `writer.pick_story` | The **scout model** gets the numbered list, the post type, your topics/avoid list and recent titles, and returns JSON: chosen story + related stories + the angle. |
| 3. Research | `research.py` | Downloads each chosen article and extracts readable text (BeautifulSoup), capped at 12k characters per source. |
| 4. Write | `writer.write_post` | The **writer model** gets your profile, the post-type instructions, the sources and the length rules. It replies in a fixed `TITLE / SUBTITLE / TAGS / === / body` format that is parsed into fields. |
| 5. Review *(optional)* | `writer.revise_post` | A second editor pass when `blog.review_pass: true`. |
| 6. Save | `db.py` | Stored in SQLite and as Markdown in `workspace/output/blog/`. Used stories are marked as seen. |
| 7. Approve | `notify/telegram.py`, dashboard | **Approval mode:** status `pending`, preview sent to Telegram. **Auto mode:** published straight away. |
| 8. Publish | `publishers/` | Each target in `publish.targets` is tried; links are stored per platform. A failure on one target doesn't block the others. |
| 9. Report | `notify/` | Telegram message with the live links (or the error). |

The writer's system prompt is built by `profile.profile_prompt()`: your profile fields plus
the text of every document switched on in `profile/documents/` (`creatoros/documents.py`
extracts text from PDF with `pypdf` and from Word with `python-docx`, then caps the size).

The `personal` post type skips steps 1-3 and uses the next unused note from
`profile/notes/` instead.

### Post statuses

```
pending ──approve──▶ published
   │  └──edit/rewrite──▶ pending
   └──skip──▶ rejected
(any publish error with no successful target) ──▶ failed
```

## Folder → post pipeline

`creatoros/modules/social/folder.py`: scan folder → convert each file to JPEG (PDF first
page via PyMuPDF, resized with Pillow) → **scout model** reads each image (vision) and
returns JSON details → **writer model** composes the post in the chosen agent role →
saved as `kind: social` posts with `media`, `targets` and `scheduled_at` →
`pipeline.approve()` publishes now or marks `scheduled` → `pipeline.publish_due()` (every
2 minutes) publishes due posts. See [FOLDER_POSTS.md](FOLDER_POSTS.md).

## Video → post pipeline

`creatoros/modules/video/videoinfo.py` (ffprobe, frame extraction, optional faster-whisper)
and `posting.py` (one `kind: video` post per file; YouTube settings and the LinkedIn caption
live in the post's `meta`). Publishers: `youtube.py` (Google OAuth, resumable upload),
`linkedin.py` (Videos API), `webhook.py` (custom platforms). See [VIDEO_POSTS.md](VIDEO_POSTS.md).

## Marketing agent

`creatoros/modules/marketing/`: `formats.py` (format specs, default targets, best times),
`planner.py` (brief → strategy + cleaned calendar, stored in the `campaigns` and `calendar`
tables), `content.py` (writes calendar items and repurposes posts; formats with no target
become `kind: draft`). The scheduler runs `content.generate_due()` every 30 minutes.
See [MARKETING.md](MARKETING.md).

## Agent roles and connections

- `creatoros/personas.py`: built-in roles plus custom; `profile.author_context()` puts
  role + profile + documents at the top of every writer prompt.
- `creatoros/connections.py`: platform catalogue (tiles, setup steps, fields), OAuth tokens,
  keys and custom webhook platforms in `data/connections.json`; `config.env()` checks `.env`
  first, then this store. Custom platforms publish as targets named `custom:<id>`.
- `creatoros/publishers/linkedin.py`: OAuth (authorization code flow with `state`),
  Images API upload, Posts API (single or multi-image).

## Model layer

`creatoros/llm.py` exposes one method, `complete(system, prompt) -> str`, behind two
provider types:

- `anthropic`: Claude through the official `anthropic` SDK. Responses are streamed
  (long posts can't hit HTTP timeouts), `effort` is passed as `output_config.effort`, and
  server-side refusal fallbacks are switched on for the models that support them.
- `openai_compatible`: any server with `POST /v1/chat/completions`: Ollama, LM Studio,
  vLLM, llama.cpp server, OpenAI, Gemini's OpenAI endpoint. `<think>` blocks from
  reasoning models are stripped.

Two roles use the layer: `writer` (quality matters) and `scout` (cheap and fast). Each
role can use a different provider, e.g. Claude for writing and a local Gemma for picking.

## Settings

- `config.yaml`: documented defaults, committed to git.
- `config.local.yaml`: your changes, written by the dashboard or Telegram commands,
  ignored by git. It is deep-merged over `config.yaml` (dicts merge, lists replace).
- `.env`: secrets only. Never exposed through the dashboard API.
- `creatoros/settings.py` validates every change (times, timezone, post types, providers,
  targets) before it is saved.

## Data

`data/creatoros.db` (SQLite):

- `posts`: id, angle, topic, sources (JSON), title, subtitle, tags (JSON), body,
  status, published (JSON `{platform: url}`), error, timestamps.
- `seen`: keys of used stories (`url:<normalised url>`) and notes (`note:<file>`), so the
  agent never covers the same thing twice.

## Security notes

- The Telegram bot ignores every chat except `TELEGRAM_CHAT_ID`.
- The dashboard binds to `127.0.0.1` by default. On a network, set `DASHBOARD_TOKEN`;
  API calls then need the `x-token` header (the page sends it from `?token=`).
- Rendered post previews are sanitised with DOMPurify.
- Note names are sanitised before they touch the filesystem.

## Video module (planned)

See [`creatoros/modules/video/README.md`](../creatoros/modules/video/README.md).
