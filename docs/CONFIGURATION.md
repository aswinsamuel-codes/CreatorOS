# Configuration

Everything can be changed in three ways:

1. **Dashboard → ⚙️ Settings** (easiest; changes apply instantly)
2. **Telegram commands** for mode and pause (`/auto`, `/approval`, `/pause`, `/resume`)
3. **Files**: edit `config.local.yaml` (your overrides) or `config.yaml` (defaults)

Your changes always go to `config.local.yaml`, which overrides `config.yaml` and is ignored
by git. Delete it (or click *Reset everything to defaults*) to start over.

Secrets live only in `.env`. See [`.env.example`](../.env.example).

## Mode: approval or auto

```yaml
approval:
  required: true                 # true = APPROVAL mode, false = AUTO mode
  auto_publish_after_minutes: 0  # approval mode only: publish anyway after N minutes (0 = never)
paused: false                    # true = skip scheduled slots
```

| Mode | What happens after a post is written |
|---|---|
| 🤝 Approval | Preview goes to Telegram and the dashboard. Nothing is published until you tap **Publish**. |
| 🤖 Auto | Published immediately to every target; Telegram gets the links. |

Switch from the dashboard header or Telegram. Tip: keep Medium on `publish_status: draft`
while you trust Auto mode, then switch to `public`.

## Schedule

```yaml
timezone: "Asia/Kolkata"     # empty = computer's local time
blog:
  schedule:
    - { time: "09:00", angle: news }
    - { time: "12:00", angle: future }
    - { time: "15:00", angle: news, days: "mon-fri" }
    - { time: "18:00", angle: business }
    - { time: "21:00", angle: personal }
    - { time: "11:00", angle: fun, days: "sat,sun" }
    - { time: "23:00", angle: news, enabled: false }
```

- `time`: 24-hour `HH:MM`.
- `angle`: any built-in or custom post type.
- `days` (optional): `mon-fri`, `sat,sun`, `mon,wed,fri`... (cron day-of-week syntax). Default: every day.
- `enabled: false` keeps a slot without running it.

## Post types (angles)

Built-in: `news`, `future`, `business`, `fun`, `personal`.

Add your own under `blog.angles`. Each needs a `label`, a `pick` instruction (what story
to choose) and a `write` instruction (how to write it):

```yaml
blog:
  angles:
    tutorial:
      label: "Hands-on tutorial"
      pick: "Pick a new tool, model or library readers can try today."
      write: "Write a step-by-step tutorial with code snippets, setup steps and common pitfalls."
    explainer:
      label: "Explain like I'm new"
      pick: "Pick a technical story that most people outside the field won't understand."
      write: "Explain it from zero with analogies, then go one level deeper for experts."
```

Using a built-in name (e.g. `news`) overrides that type's instructions.

## Writing

```yaml
blog:
  words_min: 800
  words_max: 1500
  review_pass: false     # second editor pass: better quality, about double the cost
  topics: [AI, robotics, chips, space tech, ...]
  avoid: [celebrity gossip, crypto price speculation, ...]
```

## Your profile, notes and documents

Everything here lives on your machine only (ignored by git) and is edited in the
dashboard's **My profile** tab.

| What | Where | How the writer uses it |
|---|---|---|
| Profile | `profile/profile.yaml` (created from `profile.example.yaml` on first run) | Your name, role, voice, audience, opinions and call to action, in every post |
| Notes | `profile/notes/*.md` | Each `personal` slot turns one unused note into a post |
| Documents | `profile/documents/` | Background about you in every post (see below) |

### Documents (resume, portfolio, projects...)

Upload **PDF, Word (.docx), TXT or Markdown** files up to 10 MB, or create a text
document directly. Each one is converted to plain text that you can edit (fix
extraction mistakes, remove sections you don't want used).

- Switch **Use in posts** on or off per document.
- The writer uses them to add real experience and credibility where it fits, and is told
  never to include phone numbers, emails, addresses, ID numbers or salaries.
- Size cap: 8,000 characters per document and 20,000 in total go into each prompt, which
  keeps costs predictable. Trim long documents to the parts that matter.
- Scanned PDFs (images) have no text to extract. Paste the text into a new text document instead.

Files: `profile/documents/<name>.md` (the text the writer reads),
`profile/documents/originals/` (your uploads), `profile/documents/index.json` (on/off).

## Sources

```yaml
blog:
  sources:
    hackernews: { enabled: true, limit: 40 }
    reddit: { enabled: true, limit: 15, subreddits: [technology, Futurology] }
    rss:
      - https://techcrunch.com/feed/
      - https://www.theverge.com/rss/index.xml
```

Any RSS/Atom feed works: niche blogs, arXiv categories (`https://rss.arxiv.org/rss/cs.AI`),
company blogs, Google News searches.

## Models

See [MODELS.md](MODELS.md).

## Publishing

```yaml
publish:
  targets: [medium, devto]       # medium, devto, markdown
  medium: { publish_status: draft, notify_followers: false }
  devto: { published: false, canonical_url_from_medium: true }
```

See [PUBLISHERS.md](PUBLISHERS.md).

## Dashboard

```yaml
dashboard:
  host: 127.0.0.1   # 0.0.0.0 to reach it from other machines (set DASHBOARD_TOKEN!)
  port: 8787
```

Host and port changes need a restart.
