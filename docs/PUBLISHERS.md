# Publishing

```yaml
publish:
  targets: [medium]
```

| Target | Setup | Notes |
|---|---|---|
| `medium` | `MEDIUM_TOKEN` in `.env` | Medium → Settings → Security and apps → **Integration tokens**. Medium no longer gives new tokens to every account; if the option is missing, use `markdown` and import with https://medium.com/p/import. Up to 5 tags. `publish_status`: `draft`, `public`, `unlisted`. |
| `devto` | `DEVTO_API_KEY` in `.env` | dev.to → Settings → Extensions → API keys. Up to 4 tags (letters and numbers only). With `canonical_url_from_medium: true` and `medium` listed first, the dev.to post points to Medium as the original, which is good for SEO. |
| `linkedin` | Connections tab → Connect with LinkedIn ([guide](CONNECTIONS.md)) | Official API. Text, 1 image or 2-20 images. For blog posts it shares the title, subtitle and link. |
| `markdown` | none | Writes front-matter Markdown to `workspace/output/blog/published/`, ready for Hugo, Jekyll, Astro or a manual import. |

Every generated post is also saved to `workspace/output/blog/` whatever the targets are.

## Where to post for reach (tech audiences)

| Platform | Audience | Automatable |
|---|---|---|
| Medium | Broad tech + business readers | Yes (integration token) |
| dev.to | Developers | Yes (built in) |
| Hashnode | Developers, personal domains | Yes, GraphQL API (planned) |
| LinkedIn | Professionals, founders, analysts | Yes (built in, official API) |
| X / Bluesky / Mastodon | Fast-moving tech news crowd | Yes (planned: thread from each post) |
| Hacker News, Reddit | Very large tech reach | **Share by hand.** Automated posting gets banned. |

## Writing your own publisher

A publisher is one function: it takes the post and its options and returns the public URL.

```python
# creatoros/publishers/hashnode.py
import requests
from ..config import env

def publish(post: dict, opts: dict) -> str:
    # post: id, title, subtitle, tags, body (Markdown, no H1), published (dict)
    token = env("HASHNODE_TOKEN")
    ...
    return url
```

Register it in `creatoros/publishers/__init__.py`:

```python
PUBLISHERS = {..., "hashnode": hashnode.publish}
```

Options come from `publish.<name>` in the config. Raise an exception with a clear message
on failure; the pipeline records it and still tries the other targets.
