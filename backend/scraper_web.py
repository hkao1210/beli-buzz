"""Scrapes curated journalism sources (Dickison + Liu) for restaurant chatter."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from typing import List

try:  # Optional dependency; we fall back to mock articles during linting
    feedparser = import_module("feedparser")
except ModuleNotFoundError:  # pragma: no cover - handled gracefully
    feedparser = None

CURATED_FEEDS = [
    {
        "name": "Dickison's Dining Diary",
        "url": "https://dickiesdining.com/feed/",
    },
    {
        "name": "Toronto Star – Karon Liu",
        "url": "https://www.thestar.com/authors/liu_karon.rss",
    },
    {
        "name": "Toronto Life – Food & Drink",
        "url": "https://torontolife.com/category/food/feed/",
    },
]


@dataclass
class Article:
    title: str
    summary: str
    url: str
    source: str
    published: datetime


FALLBACK_ARTICLES = [
    Article(
        title="Toronto chef revives northern Thai classics",
        summary="Pai's khao soi and gaeng hang lay continue to dominate downtown buzz.",
        url="https://example.com/pai-khao-soi",
        source="Mock: Dickison",
        published=datetime.utcnow(),
    ),
    Article(
        title="Why Seven Lives still has the best tacos",
        summary="Karon Liu dissects the perfectly battered Baja fish taco.",
        url="https://example.com/seven-lives-tacos",
        source="Mock: Liu",
        published=datetime.utcnow(),
    ),
]


def _parse_feed(feed: dict) -> List[Article]:
    if feedparser is None:
        raise RuntimeError("feedparser not installed")
    parsed = feedparser.parse(feed["url"])
    articles: List[Article] = []
    for entry in parsed.entries[:5]:
        summary = getattr(entry, "summary", getattr(entry, "description", "")).strip()
        published_parsed = getattr(entry, "published_parsed", None)
        published = datetime(*published_parsed[:6]) if published_parsed else datetime.utcnow()
        articles.append(
            Article(
                title=entry.title,
                summary=summary,
                url=entry.link,
                source=feed["name"],
                published=published,
            )
        )
    return articles


def fetch_curated_articles(max_articles: int = 12) -> List[dict]:
    articles: List[Article] = []
    for feed in CURATED_FEEDS:
        try:
            articles.extend(_parse_feed(feed))
        except Exception as exc:  # pragma: no cover - network dependent
            print(f"Failed to parse {feed['name']}: {exc}")
            continue

    if not articles:
        articles = FALLBACK_ARTICLES

    articles.sort(key=lambda article: article.published, reverse=True)
    serialized = [
        {
            "title": art.title,
            "summary": art.summary,
            "url": art.url,
            "source": art.source,
            "published": art.published.isoformat(),
        }
        for art in articles[:max_articles]
    ]
    return serialized


if __name__ == "__main__":  # pragma: no cover
    print(fetch_curated_articles())
