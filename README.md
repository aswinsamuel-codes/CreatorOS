# CreatorOS

An open-source AI content studio that runs on your own machine. It finds the day's most
interesting tech stories, writes posts in **your** voice, asks for your approval on
Telegram or a local dashboard, and publishes them to Medium (and more).

Works with **Claude**, **OpenAI**, **Gemini**, or **local models** (Ollama, LM Studio, vLLM),
so you can run it on a laptop with an API key or on your own GPU cluster.

## What it does

```
Scout  -> Hacker News, Reddit, TechCrunch, The Verge, Ars Technica, Wired, MIT Tech Review
Pick   -> an editor model picks the best fresh story for the slot's post type
Read   -> fetches the source articles
Write  -> 800-1500 word original post, tone matched to the topic, in your voice
Ask    -> sends a preview to Telegram: Publish / Edit / Skip / Full text
Post   -> Medium (draft or public), dev.to, or Markdown files
Report -> sends you the live link
```

### Folder → post (bulk certificates and more)
Point the agent at a folder of certificates, badges, project screenshots or event photos.
It reads every file (images and PDFs), writes LinkedIn posts in your voice, and posts them
as one multi-image post or as a series (e.g. one a day) after your approval.
See [docs/FOLDER_POSTS.md](docs/FOLDER_POSTS.md).

### 📣 Marketing agent
Give it a goal, audience and offer. It plans a strategy (positioning, content pillars, KPIs)
and a dated content calendar across LinkedIn posts, X threads, Instagram captions, blog
articles, short-video scripts and newsletters, then writes each piece before it's due.
**♻️ Repurpose** turns any post into versions for other formats.
See [docs/MARKETING.md](docs/MARKETING.md).

### Video → post (YouTube, LinkedIn)
Give it a video or a folder of videos. It watches sample frames (and the transcript), writes
the YouTube title, description, tags and chapters plus a LinkedIn caption, and uploads after
your approval. Vertical clips go out as YouTube Shorts. See [docs/VIDEO_POSTS.md](docs/VIDEO_POSTS.md).

### Connections, made for everyone
Click a platform's tile and follow the steps: Claude, Telegram, LinkedIn, YouTube, Medium,
dev.to. LinkedIn and YouTube use their official login pages, so no passwords are stored. Use
**＋ Add a platform** to connect any other app through its API or a Zapier/Make/n8n webhook.
See [docs/CONNECTIONS.md](docs/CONNECTIONS.md).

### Agent roles
Choose how the agent thinks and writes: tech blogger, marketing strategist, developer
advocate, content creator, personal-brand coach, startup founder, teacher, or your own
custom role.

### Two modes
| Mode | Behaviour |
|---|---|
| 🤝 **Approval** (default) | Every post waits for your OK on Telegram or the dashboard |
| 🤖 **Auto** | The agent publishes on its own and sends you the links |

Switch from the dashboard header or Telegram (`/auto`, `/approval`), and pause the agent
any time (`/pause`, `/resume`).

### Everything is customisable
Schedule times, days, timezone, post types (including your own), word count, topics,
sources, models, providers and publish targets can all be changed in the dashboard's
**⚙️ Settings** tab. Changes apply instantly and are saved to `config.local.yaml`.

Built-in post types: `news`, `future` (question-led), `business` (opportunities), `fun`,
`personal` (built from your own notes in `profile/notes/`).

Default daily schedule: 09:00 news · 12:00 future · 15:00 news · 18:00 business ·
21:00 personal.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # optional: keys can also be added in the dashboard's Connections tab
python -m creatoros check
```

### Medium token
Medium → Settings → Security and apps → **Integration tokens**. Paste it into `MEDIUM_TOKEN`.
Medium no longer issues new tokens to every account; if you don't see the option, use the
`markdown` or `devto` targets and import into Medium with https://medium.com/p/import.

### Telegram approval bot
1. In Telegram, message **@BotFather** → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN`.
2. Send any message to your new bot.
3. Run `python -m creatoros telegram-chat-id` and copy the id into `TELEGRAM_CHAT_ID`.

The bot only responds to that chat id. Commands: `/mode`, `/approval`, `/auto`, `/pause`,
`/resume`, `/write [type] [topic]`, `/status`. See [docs/TELEGRAM.md](docs/TELEGRAM.md).

### Your profile
In the dashboard's **My profile** tab (or the files under `profile/`):
- fill in your details and writing voice,
- add notes with your own ideas, drafts and experiences,
- **upload documents** such as your resume, portfolio or project write-ups (PDF, Word, TXT,
  MD). They become editable text the writer uses as background about you, and private
  details like phone or email are never put into posts.

All of it stays on your machine and is ignored by git.

## Use it

```powershell
python -m creatoros scout                     # see today's candidate stories
python -m creatoros write --angle news        # write one post now
python -m creatoros write --angle future --topic "AI agents in healthcare"
python -m creatoros list
python -m creatoros publish 1
python -m creatoros run                       # 24/7: schedule + bot + dashboard
```

Dashboard: http://localhost:8787

### Run automatically on Windows
Use `start_creatoros.bat`. To start it at login: Task Scheduler → Create Basic Task →
"When I log on" → Start a program → `start_creatoros.bat`. The PC must be awake at the
scheduled times (Settings → System → Power → set sleep to "Never" while plugged in).

## Local models / your own cluster

In `config.yaml`:

```yaml
models:
  writer: { provider: ollama, model: gemma3:27b }
providers:
  ollama:
    type: openai_compatible
    base_url: http://<cluster-ip>:11434/v1
```

On a shared machine, set `dashboard.host: 0.0.0.0` and a `DASHBOARD_TOKEN` in `.env`, then
open `http://<host>:8787/?token=<your token>`.

## Documentation

| Doc | Covers |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | How the pipeline, scheduler, bot and dashboard fit together |
| [Configuration](docs/CONFIGURATION.md) | Modes, schedule, custom post types, sources, every setting |
| [Models](docs/MODELS.md) | Claude, Ollama/local clusters, OpenAI, Gemini and more |
| [Publishers](docs/PUBLISHERS.md) | Medium, dev.to, Markdown, writing your own publisher |
| [Telegram](docs/TELEGRAM.md) | Bot setup, approval buttons, commands |
| [Connections](docs/CONNECTIONS.md) | LinkedIn official login, API keys |
| [Folder → post](docs/FOLDER_POSTS.md) | Turning certificates/screenshots/photos into posts |
| [Video → post](docs/VIDEO_POSTS.md) | YouTube/LinkedIn video uploads with AI-written metadata |
| [Marketing agent](docs/MARKETING.md) | Campaign strategy, content calendar, repurposing |
| [Contributing](CONTRIBUTING.md) | Dev setup, tests, guidelines, releases |
| [Changelog](CHANGELOG.md) | What changed in each version |

## Tests

```powershell
python tests/test_pipeline.py    # full pipeline with a fake model: no keys, no cost
```

## Project layout

```
creatoros/
  llm.py            model providers (Claude + any OpenAI-compatible server)
  modules/blog/     scout, angles, writer, pipeline
  modules/video/    video editor module (planned, see its README)
  publishers/       medium, devto, markdown  (add your own: one function)
  notify/           Telegram approval bot
  dashboard/        local web dashboard
  scheduler.py      daily slots (reload live)
  settings.py       validation for settings changes
docs/               documentation
tests/              pipeline tests (fake model)
profile/            your details + your own notes
workspace/          clips, references, music, voices, output
```

## Roadmap
- v0.2: Hashnode, LinkedIn and X/Bluesky threads, cover images
- v0.3: video module (clips folder, reference-style editing, captions, voiceover)
- v0.4: blog ↔ video conversion, newsletter
- v1.0: plugin system, packaged app, MCP server

## Responsible use
Posts are drafted by AI from public sources. Keep the approval step on, check facts before
publishing, and follow each platform's rules on AI-generated content.

License: MIT
