# Marketing agent

Tell CreatorOS what you want to achieve. It plans the campaign, writes every piece on time,
and keeps everything going through your usual approval flow.

## 1. Create a campaign

**📣 Marketing** tab → *New campaign*:

| Field | Example |
|---|---|
| Goal | Grow my LinkedIn as a cloud engineer and get 3 freelance leads |
| Audience | Startup founders and CTOs |
| Key message / offer | I help startups cut AWS costs |
| Links | github.com/me, mysite.com/book-a-call |
| Formats → where they go | LinkedIn post → LinkedIn · Short video script → draft for me |
| Start, weeks, pieces per week | Tomorrow, 2 weeks, 5 per week |
| Agent role | Marketing strategist (or any role) |
| Anything else | Launching my course on Dec 15; mention it in the last week |

Click **🧠 Plan my campaign**. In about a minute you get:

- **Positioning**: how you should come across, and why it matters to the audience
- **Content pillars**: 3-5 themes the content rotates through
- **Audience insights**, **KPIs** and **tips**
- **Content calendar**: every piece with date and time, format, pillar, topic, hook and call
  to action, at good default posting times (no more than 1 in 5 pieces is promotional)

## 2. Adjust the calendar

Each row can be rescheduled (change the date/time), edited (✏️ topic and hook), skipped, or
written immediately (**Write now**). **✍️ Write next 7 days now** writes the coming week in one go.

## 3. It writes on time

While a campaign is **active**, each piece is written automatically `marketing.lead_hours`
(default 24) hours before its time:

- **Approval mode**: it lands in Posts and on Telegram for your OK, then publishes at its time.
- **Auto mode**: it's scheduled and publishes at its time.
- **Drafts** (video scripts, newsletters, and any format without a connected platform) are
  written for you to use yourself: a 📋 Copy button and a ✔ Mark ready button, nothing is published.

Pause or resume a campaign any time; the global ⏸ Pause stops everything.

## Formats

| Format | Published to | Notes |
|---|---|---|
| LinkedIn post | LinkedIn | Strong first line, 900-1600 characters, 3-5 hashtags |
| X / Twitter thread | a custom platform (e.g. Zapier → X), otherwise a draft | 4-8 numbered posts |
| Instagram caption | a custom platform, otherwise a draft | Includes a "Visual idea" line and hashtags |
| Blog article | your blog targets from Settings (Medium, dev.to…) | Markdown, 900-1500 words |
| Short video script | draft | Hook, scenes with on-screen text and b-roll, CTA, caption |
| Newsletter / email | draft | Subject, preview line, body |

Connect X, Instagram and other apps with **＋ Add a platform** on the Connections tab
([guide](CONNECTIONS.md)); they then appear in the "where they go" dropdowns.

## ♻️ Repurpose any post

Every post (blog, LinkedIn, video, campaign piece) has a **♻️ Repurpose** button. Pick formats
(e.g. X thread + short video script + newsletter) and CreatorOS writes native versions of the
same ideas, each as a new post for your approval.

## Settings

```yaml
marketing:
  lead_hours: 24          # write each piece this long before it's due
  best_times:             # default posting time per format (starting points; tune for your audience)
    linkedin_post: "09:00"
    x_thread: "12:30"
    instagram_caption: "18:00"
    blog_post: "10:00"
    video_script: "15:00"
    newsletter: "08:00"
```

Edit in **Settings → Advanced (YAML)**.

## Honesty rules built in

The planner and writer are told never to invent statistics, clients, testimonials or results.
They only use facts from your brief, your profile and documents, or general knowledge. Proof-type
content is planned only around real proof you've given.

## Coming next

- Performance tracking (YouTube views, likes and comments first) so the planner learns what works.
- Telegram commands for campaigns.
