"""
Blog Scraper using RSS Feeds + Trafilatura
==========================================
Scrapes Toronto food blogs and publications via RSS feeds.
Uses trafilatura for full article extraction when needed.
"""

import logging
import re
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional
from enum import Enum
import argparse
import json
import csv
import sys
from pathlib import Path

import feedparser
from dateutil import parser as date_parser
from dotenv import load_dotenv
from shared.models import SourceType
import trafilatura

load_dotenv()

logger = logging.getLogger(__name__)


# =============================================================================
# MODELS (or import from shared.models.py)
# =============================================================================

@dataclass
class ScrapedContent:
    """Represents scraped content from any source."""
    source_type: SourceType
    source_url: str
    title: str
    raw_text: str
    source_id: Optional[str] = None
    author: Optional[str] = None
    subreddit: Optional[str] = None  # For Reddit
    reddit_score: Optional[int] = None
    reddit_num_comments: Optional[int] = None
    posted_at: Optional[datetime] = None
    scraped_at: Optional[datetime] = None

    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.now()


# =============================================================================
# FEED CONFIGURATION
# =============================================================================

@dataclass
class FeedConfig:
    """Configuration for an RSS feed source."""
    name: str
    feed_url: str
    food_filter: bool = False  # If True, filter for food-related content


# Verified working RSS feeds (December 2025)
BLOG_FEEDS: List[FeedConfig] = [
    # Major Toronto Publications
    FeedConfig(
        name="BlogTO",
        feed_url="https://feeds.feedburner.com/blogto",
        food_filter=True,  
    ),
    FeedConfig(
        name="Streets of Toronto - Food",
        feed_url="https://streetsoftoronto.com/category/food/feed/",
    ),
    FeedConfig(
        name="NOW Toronto",
        feed_url="https://nowtoronto.com/feed/",
        food_filter=True,
    ),
    FeedConfig(
        name="Narcity Toronto",
        feed_url="https://www.narcity.com/feeds/toronto.rss",
        food_filter=True,
    ),
    # Toronto Food Bloggers
    FeedConfig(
        name="Toronto Food Blog",
        feed_url="https://torontofoodblog.com/feed/",
    ),
    FeedConfig(
        name="Chocolates & Chai",
        feed_url="https://www.chocolatesandchai.com/feed/",
    ),
    FeedConfig(
        name="Gastro World",
        feed_url="https://www.gastroworld.ca/feeds/posts/default",
    ),
]

# Reddit feeds
REDDIT_FEEDS: List[FeedConfig] = [
    FeedConfig(name="FoodToronto", feed_url="https://www.reddit.com/r/FoodToronto/new/.rss"),
    FeedConfig(name="Toronto", feed_url="https://www.reddit.com/r/toronto/.rss"),
    FeedConfig(name="askTO", feed_url="https://www.reddit.com/r/askTO/new/.rss", food_filter=True),
]


# =============================================================================
# SCRAPER
# =============================================================================

class ContentScraper:
    """Scrapes Toronto food blogs using RSS feeds + trafilatura."""

    FOOD_KEYWORDS = frozenset({
        "restaurant", "food", "eat", "dining", "chef", "menu", "brunch",
        "dinner", "lunch", "cafe", "coffee", "bar", "cocktail", "pizza",
        "sushi", "ramen", "taco", "burger", "bakery", "dessert", "patio",
        "kitchen", "cuisine", "takeout", "delivery", "reservation", "opening",
        "diner", "bistro", "eatery", "gastropub", "foodie", "michelin",
        "taste", "dim sum", "noodle", "bbq", "steakhouse", "vegan",
        "vegetarian", "thai", "indian", "italian", "mexican", "korean",
        "japanese", "chinese", "vietnamese", "greek", "middle eastern",
    })

    def __init__(self):
        pass

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _parse_date(self, entry) -> Optional[datetime]:
        """Parse date from RSS entry."""
        for field in ("published", "updated", "created"):
            val = getattr(entry, field, None)
            if val:
                try:
                    return date_parser.parse(val)
                except (ValueError, TypeError):
                    continue
        return None

    def _get_entry_content(self, entry) -> str:
        """Extract content from RSS entry."""
        if hasattr(entry, "content") and entry.content:
            return entry.content[0].value
        return getattr(entry, "summary", "") or getattr(entry, "description", "") or ""

    def _is_food_related(self, title: str, content: str) -> bool:
        """Check if content is food-related."""
        text = f"{title} {content}".lower()
        return any(kw in text for kw in self.FOOD_KEYWORDS)

    def _clean_html(self, html: str) -> str:
        """Strip HTML tags."""
        return re.sub(r"<[^>]+>", " ", html).strip()

    def _is_recent(self, posted_at: Optional[datetime], days_back: int) -> bool:
        """Check if date is within days_back."""
        if not posted_at:
            return True  # Include if no date
        cutoff = datetime.now() - timedelta(days=days_back)
        posted_naive = posted_at.replace(tzinfo=None) if posted_at.tzinfo else posted_at
        return posted_naive >= cutoff

    # -------------------------------------------------------------------------
    # Article Extraction
    # -------------------------------------------------------------------------

    def extract_full_article(self, url: str) -> Optional[str]:
        """
        Extract full article text from URL using trafilatura.
        Use this when RSS only provides a summary.
        """
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(
                    downloaded,
                    include_comments=False,
                    include_tables=False,
                    no_fallback=False,
                )
                return text
        except Exception as e:
            logger.debug(f"Failed to extract {url}: {e}")

        return None

    # -------------------------------------------------------------------------
    # RSS Scraping
    # -------------------------------------------------------------------------

    def scrape_feed(
        self,
        config: FeedConfig,
        source_type: SourceType,
        limit: int = 25,
        days_back: int = 30,
        fetch_full_text: bool = False,
    ) -> List[ScrapedContent]:
        """Scrape a single RSS feed."""
        results = []

        try:
            feed = feedparser.parse(config.feed_url)

            if feed.bozo and not feed.entries:
                logger.warning(f"Failed to parse {config.name}: {feed.bozo_exception}")
                return results

            for entry in feed.entries[:limit]:
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()
                raw_content = self._get_entry_content(entry)
                content = self._clean_html(raw_content)
                posted_at = self._parse_date(entry)

                if not self._is_recent(posted_at, days_back):
                    continue

                if config.food_filter and not self._is_food_related(title, content):
                    continue

                if fetch_full_text and len(content) < 500 and link:
                    full_text = self.extract_full_article(link)
                    if full_text:
                        content = full_text

                results.append(
                    ScrapedContent(
                        source_type=source_type,
                        source_url=link,
                        source_id=link,
                        title=title,
                        raw_text=content,
                        author=getattr(entry, "author", None),
                        posted_at=posted_at,
                    )
                )

            logger.info(f"Scraped {len(results)} items from {config.name}")

        except Exception as e:
            logger.error(f"Error scraping {config.name}: {e}")

        return results

    def scrape_blogs(
        self,
        limit_per_feed: int = 25,
        days_back: int = 30,
        fetch_full_text: bool = False,
    ) -> List[ScrapedContent]:
        """Scrape all blog RSS feeds."""
        results = []

        for config in BLOG_FEEDS:
            items = self.scrape_feed(
                config,
                source_type=SourceType.BLOG,
                limit=limit_per_feed,
                days_back=days_back,
                fetch_full_text=fetch_full_text,
            )
            results.extend(items)

        logger.info(f"Total from blog feeds: {len(results)}")
        return results

    def scrape_reddit(
        self,
        limit_per_feed: int = 50,
        days_back: int = 7,
    ) -> List[ScrapedContent]:
        """Scrape Reddit RSS feeds."""
        results = []

        for config in REDDIT_FEEDS:
            try:
                feed = feedparser.parse(config.feed_url)

                for entry in feed.entries[:limit_per_feed]:
                    title = getattr(entry, "title", "").strip()
                    link = getattr(entry, "link", "").strip()
                    content = self._clean_html(self._get_entry_content(entry))
                    posted_at = self._parse_date(entry)

                    if not self._is_recent(posted_at, days_back):
                        continue

                    if config.food_filter and not self._is_food_related(title, content):
                        continue

                    results.append(
                        ScrapedContent(
                            source_type=SourceType.SOCIAL,
                            source_url=link,
                            source_id=link,
                            title=title,
                            raw_text=content,
                            subreddit=config.name,
                            posted_at=posted_at,
                        )
                    )

                logger.info(
                    f"Scraped {len([r for r in results if r.subreddit == config.name])} "
                    f"from r/{config.name}"
                )

            except Exception as e:
                logger.error(f"Error scraping r/{config.name}: {e}")

        logger.info(f"Total from Reddit: {len(results)}")
        return results

    def scrape_all(
        self,
        blog_limit: int = 25,
        reddit_limit: int = 50,
        blog_days_back: int = 30,
        reddit_days_back: int = 7,
        fetch_full_text: bool = False,
    ) -> List[ScrapedContent]:
        """Scrape all sources (blogs + Reddit)."""
        results = []

        results.extend(
            self.scrape_blogs(
                limit_per_feed=blog_limit,
                days_back=blog_days_back,
                fetch_full_text=fetch_full_text,
            )
        )

        results.extend(
            self.scrape_reddit(
                limit_per_feed=reddit_limit,
                days_back=reddit_days_back,
            )
        )

        logger.info(f"Total scraped: {len(results)}")
        return results



def _serialize_item(item: ScrapedContent) -> dict:
    d = asdict(item)
    # Datetime -> ISO
    for k in ("posted_at", "scraped_at"):
        if d.get(k):
            try:
                d[k] = d[k].isoformat()
            except Exception:
                d[k] = str(d[k])
    if isinstance(d.get("source_type"), dict):
        d["source_type"] = d["source_type"].get("value") if d["source_type"].get("value") else str(d["source_type"])
    else:
        d["source_type"] = getattr(item.source_type, "value", str(item.source_type))
    return d


def _write_json(path: Path, items: list):
    with path.open("w", encoding="utf-8") as f:
        json.dump([_serialize_item(i) for i in items], f, ensure_ascii=False, indent=2)


def _write_csv(path: Path, items: list):
    if not items:
        path.write_text("")
        return
    rows = [_serialize_item(i) for i in items]
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Blog + Reddit RSS scraper CLI")
    parser.add_argument("--source", choices=["blogs", "reddit", "all"], default="all", help="Which sources to scrape")
    parser.add_argument("--blog-limit", type=int, default=25, help="Limit per blog feed")
    parser.add_argument("--reddit-limit", type=int, default=50, help="Limit per reddit feed")
    parser.add_argument("--blog-days", type=int, default=30, help="Days back for blogs")
    parser.add_argument("--reddit-days", type=int, default=7, help="Days back for reddit")
    parser.add_argument("--fetch-full", action="store_true", help="Fetch full article text when summary is short")
    parser.add_argument("--output", type=Path, help="Path to write results (json or csv). If omitted, prints to stdout")
    parser.add_argument("--format", choices=["json", "csv"], default="json", help="Output format when --output is used")
    parser.add_argument("--log-level", default="INFO", help="Logging level")

    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(asctime)s [%(levelname)s] %(message)s")

    scraper = ContentScraper()
    results = []

    if args.source in ("blogs", "all"):
        logging.info("Starting blog feeds scrape")
        blogs = scraper.scrape_blogs(limit_per_feed=args.blog_limit, days_back=args.blog_days, fetch_full_text=args.fetch_full)
        results.extend(blogs)
        logging.info(f"Collected {len(blogs)} blog items")

    if args.source in ("reddit", "all"):
        logging.info("Starting reddit scrape")
        reddit = scraper.scrape_reddit(limit_per_feed=args.reddit_limit, days_back=args.reddit_days)
        results.extend(reddit)
        logging.info(f"Collected {len(reddit)} reddit items")

    total = len(results)
    logging.info(f"Total items collected: {total}")

    if args.output:
        out = args.output
        out.parent.mkdir(parents=True, exist_ok=True)
        if args.format == "json":
            _write_json(out, results)
        else:
            _write_csv(out, results)
        logging.info(f"Wrote {total} items to {out}")
    else:
        # Print a compact summary to stdout
        for item in results[:20]:
            print(f"[{item.source_type.value}] {item.title}\n  {item.source_url}\n")
        if total > 20:
            print(f"... (and {total-20} more items)\n")


if __name__ == "__main__":
    main()