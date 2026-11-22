# Changelog

All notable changes are listed here. The project follows [Semantic Versioning](https://semver.org).

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
