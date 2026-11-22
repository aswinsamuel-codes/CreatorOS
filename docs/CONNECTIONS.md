# Connections

Everything is connected from the dashboard's **🔌 Connections** tab. No files or code are
needed.

```
[Claude AI] [Telegram] [LinkedIn] [YouTube] [Medium] [dev.to] [your platforms…] [＋ Add a platform]
```

Click a tile to open its setup window:
- numbered steps, each with an **open ↗** button that takes you to the right page,
- the boxes to paste into,
- **Save**, **Test** (checks the key really works), and **Connect** for platforms with an
  official login (LinkedIn, YouTube),
- for Telegram, a **Find my chat ID** button that fills the chat ID in for you.

Keys are stored only on your computer in `data/connections.json` (ignored by git). If a value
is also set in `.env`, the `.env` value wins and the box shows "saved (from .env)".

## Official login vs passwords

LinkedIn and YouTube use their official login pages (OAuth): you sign in on their site, and
CreatorOS gets permission to post without ever seeing your password. You can revoke it any time
in that platform's settings. Bots that type your password into a website break the platforms'
rules and can get accounts restricted, so CreatorOS doesn't do that.

## ＋ Add a platform (any app)

For platforms without a built-in connector (Instagram, Facebook, X, Threads, Discord, Slack,
WordPress, Notion…), add a **custom platform**:

1. In **Zapier**, **Make**, **n8n**, **IFTTT** or **Pipedream**, create an automation:
   *Webhook (catch hook)* → *post to the app you want*.
2. In CreatorOS click **＋ Add a platform**, paste the webhook URL, name it, and click **Save**.
3. Click **Send test**, then map the fields in your automation (text, title, media).
4. Tick the new platform under *Post to* (Folder → post, Video → post, or Settings).

Apps with their own API work the same way: paste the API URL, the header name it expects
(e.g. `Authorization`) and the key (e.g. `Bearer abc123`).

What CreatorOS sends (JSON):

```json
{
  "source": "CreatorOS", "test": false, "post_id": 12, "kind": "blog | social | video",
  "title": "…", "text": "ready-to-post text", "description": "long text / blog body",
  "tags": ["…"], "hashtags": ["#…"], "link": "first published URL, if any",
  "media": [{"type": "image|video", "filename": "…", "mime": "…", "alt": "…", "data_base64": "…"}]
}
```

Reply with `{"url": "…"}` and that link is shown on the post. Media is included up to 25 MB
per post (untick *Include images/video* to send text only).

## Platform notes

### LinkedIn
- The app must be linked to a LinkedIn Page (a simple personal page works).
- Products needed: *Sign In with LinkedIn using OpenID Connect* and *Share on LinkedIn*.
- Login lasts 60 days; the tile shows the days left. Click *Reconnect* when it runs out.
- If LinkedIn reports a version error, set `publish.linkedin.api_version` to a recent month,
  e.g. `"202611"`, in Settings → Advanced.
- Already have a token? `LINKEDIN_ACCESS_TOKEN` + `LINKEDIN_PERSON_URN` in `.env` take priority.

### YouTube
- Google Cloud project with *YouTube Data API v3* enabled, an OAuth consent screen (External,
  with yourself as a test user), and an OAuth client of type *Web application*.
- CreatorOS keeps a refresh token, so you only connect once.
- Uploads from unaudited projects are private; see [VIDEO_POSTS.md](VIDEO_POSTS.md).

### Redirect URLs
Open the dashboard as `http://localhost:8787` when connecting, so the redirect URL matches the
one you added to the app. On another machine, add that machine's address as an extra redirect URL.

### Telegram
After saving the bot token and chat ID, restart CreatorOS so the bot starts listening for button
presses.
