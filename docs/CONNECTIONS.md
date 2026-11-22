# Connections

The **🔌 Connections** tab is where you connect platforms. There are two kinds:

| Kind | Platforms | How |
|---|---|---|
| **Official login (OAuth)** | LinkedIn | Click *Connect*, sign in on LinkedIn's own page, approve. CreatorOS never sees your password. |
| **API key / token** | Medium, dev.to, Telegram, Claude | Paste the key and click *Save*. |

Keys entered here are stored only on your computer in `data/connections.json` (ignored by
git). Anything set in `.env` takes priority and is shown as "set in .env".

## Why not log in with my username and password?

Typing your password into a bot that drives a browser breaks LinkedIn's User Agreement
(and most platforms' rules), often triggers security checks, and can get the account
restricted. It also means storing your password. The official OAuth login is the safe,
allowed way: you can revoke it any time from LinkedIn's settings.

## LinkedIn setup (one time, about 10 minutes)

1. Go to https://developer.linkedin.com → **Create app**. LinkedIn asks you to link the app to
   a LinkedIn **Company Page**; create a simple page for yourself if you don't have one.
2. In the app's **Products** tab, add:
   - **Sign In with LinkedIn using OpenID Connect**
   - **Share on LinkedIn**
3. In the **Auth** tab, under *Authorized redirect URLs*, add the URL shown on the
   Connections tab, normally:
   `http://localhost:8787/api/connections/linkedin/callback`
4. Copy the **Client ID** and **Client Secret** into the LinkedIn card and click **Save**.
5. Click **🔗 Connect with LinkedIn**, sign in and allow access.

Open the dashboard as `http://localhost:8787` (not `127.0.0.1`) so the redirect URL matches.
If you run CreatorOS on another machine, add that address's callback URL to the app as well.

The login lasts **60 days**; the card shows the days left. Click *Reconnect* when it expires.

### What CreatorOS can do on LinkedIn

- Post text, a single image, or a multi-image post (2-20 images) on your personal profile.
- Share a teaser and link for blog posts (add `linkedin` to `publish.targets`).
- Visibility: `publish.linkedin.visibility: PUBLIC` or `CONNECTIONS`.

The LinkedIn API is versioned monthly. If LinkedIn returns a version error, set
`publish.linkedin.api_version` to a recent month, e.g. `"202611"`.

### Advanced: tokens in .env

If you already have a token: set `LINKEDIN_ACCESS_TOKEN` and `LINKEDIN_PERSON_URN`
(`urn:li:person:...`) in `.env`. These take priority over the dashboard login.

## Telegram changes

After saving a new Telegram token or chat id, restart CreatorOS so the bot starts
listening for button presses.
