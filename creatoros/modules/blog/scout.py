"""Find today's trending tech stories from Hacker News, Reddit and RSS feeds."""

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import feedparser
import requests

from ... import db
from ...config import log

UA = {"User-Agent": "CreatorOS/0.1 (open-source content agent)"}
HN = "https://hacker-news.firebaseio.com/v0"


def _hn_item(item_id: int) -> dict | None:
    try:
        it = requests.get(f"{HN}/item/{item_id}.json", timeout=10).json()
    except Exception:
        return None
    if not it or it.get("type") != "story" or not it.get("url"):
        return None
    return {
        "title": it["title"],
        "url": it["url"],
        "source": "Hacker News",
        "score": it.get("score", 0),
        "comments": it.get("descendants", 0),
    }


def hackernews(limit: int = 40) -> list[dict]:
    ids = requests.get(f"{HN}/topstories.json", timeout=15).json()[:limit]
    with ThreadPoolExecutor(max_workers=10) as pool:
        return [x for x in pool.map(_hn_item, ids) if x]


def reddit(subreddits: list[str], limit: int = 15) -> list[dict]:
    out = []
    for sub in subreddits:
        try:
            r = requests.get(f"https://www.reddit.com/r/{sub}/top.json?t=day&limit={limit}", headers=UA, timeout=8)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            log.warning("Reddit isn't responding from this network - skipping it this run")
            break
        except Exception as e:
            log.warning("Reddit r/%s failed: %s", sub, e)
            continue
        for child in r.json().get("data", {}).get("children", []):
            d = child["data"]
            if d.get("stickied") or d.get("over_18"):
                continue
            url = d.get("url_overridden_by_dest") or f"https://www.reddit.com{d['permalink']}"
            out.append({"title": d["title"], "url": url, "source": f"r/{sub}", "score": d.get("score", 0),
                        "comments": d.get("num_comments", 0)})
    return out


def rss(feeds: list[str], per_feed: int = 12) -> list[dict]:
    out = []
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url, agent=UA["User-Agent"])
        except Exception as e:
            log.warning("RSS %s failed: %s", feed_url, e)
            continue
        name = feed.feed.get("title", urlparse(feed_url).netloc)
        for e in feed.entries[:per_feed]:
            if e.get("link"):
                out.append({"title": e.get("title", ""), "url": e["link"], "source": name, "score": 0, "comments": 0})
    return out


def _norm(url: str) -> str:
    p = urlparse(url)
    return f"{p.netloc.removeprefix('www.')}{p.path.rstrip('/')}".lower()


def gather(cfg: dict) -> list[dict]:
    src = cfg["blog"]["sources"]
    found: list[dict] = []
    if src.get("hackernews", {}).get("enabled"):
        try:
            found += hackernews(src["hackernews"].get("limit", 40))
        except Exception as e:
            log.warning("Hacker News failed: %s", e)
    if src.get("reddit", {}).get("enabled"):
        found += reddit(src["reddit"].get("subreddits", []), src["reddit"].get("limit", 15))
    if src.get("rss"):
        found += rss(src["rss"])

    seen = db.seen_keys()
    unique, keys = [], set()
    for c in found:
        k = _norm(c["url"])
        if k in keys or f"url:{k}" in seen or not c["title"]:
            continue
        keys.add(k)
        c["key"] = f"url:{k}"
        unique.append(c)
    log.info("Scout found %d fresh stories (%d raw)", len(unique), len(found))
    return unique
