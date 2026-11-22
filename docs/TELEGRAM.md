# Telegram bot

## Setup

1. In Telegram, open **@BotFather** → `/newbot` → choose a name → copy the token.
2. Put it in `.env` as `TELEGRAM_BOT_TOKEN`.
3. Send any message to your new bot.
4. Run `python -m creatoros telegram-chat-id` and copy the printed `TELEGRAM_CHAT_ID=...`
   line into `.env`.
5. Run `python -m creatoros check`. You should see `OK Telegram - bot @yourbot`.

The bot only responds to your chat id. Everyone else is ignored.

## Approving posts

Each new post arrives with its title, tags and a preview, plus buttons:

| Button | Action |
|---|---|
| ✅ Publish | Publish to all targets now; you get the links back |
| ❌ Skip | Mark as rejected |
| ✏️ Edit | Reply with what to change ("shorter, more casual title") and the AI rewrites it, then sends it back for approval |
| 📄 Full text | Sends the whole post as a `.md` file |

## Commands

| Command | Does |
|---|---|
| `/mode` | Show the current mode and whether the schedule is paused |
| `/approval` | Approval mode: every post waits for your OK |
| `/auto` | Auto mode: publish automatically, just send links |
| `/pause` / `/resume` | Stop or restart the daily schedule |
| `/write [type] [topic]` | Write a post now, e.g. `/write future AI in farming` or `/write` |
| `/status` | Last 8 posts and their status |

## Why Telegram rather than email

Telegram gives instant push notifications, tap-to-approve buttons, and edits by simple
reply, all for free and with no mail server. Email can't easily carry working buttons, so
approving would mean opening the dashboard anyway.
