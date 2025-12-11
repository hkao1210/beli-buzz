"""
Reddit Scraper using JSON endpoints
===================================
Scrapes Toronto food-related subreddits for restaurant mentions.
No API key required - uses public .json endpoints.
"""

import logging
from datetime import datetime
from typing import List, Optional

import httpx
from dotenv import load_dotenv
from models import ScrapedContent, SourceType

load_dotenv()

logger = logging.getLogger(__name__)


# Toronto-focused subreddits for food content
TORONTO_SUBREDDITS = [
    "askTO",
    "toronto",
    "FoodToronto",
    "TorontoFood",
]

# Search keywords to find restaurant discussions
FOOD_KEYWORDS = [
    "restaurant",
    "best place to eat",
    "where to eat",
    "recommend",
    "brunch",
    "dinner",
    "ramen",
    "pizza",
    "sushi",
    "thai",
    "italian",
    "indian",
    "korean",
    "chinese",
    "vietnamese",
    "burger",
    "hidden gem",
]

BASE_URL = "https://old.reddit.com"
HEADERS = {
    "User-Agent": "BellyBuzz/1.0 (Toronto food recommendation app)"
}


class RedditScraper:
    """
    Scrapes Reddit for Toronto restaurant mentions using public JSON endpoints.
    No API credentials required.
    """

    def __init__(self):
        self.client = httpx.Client(headers=HEADERS, timeout=30.0)

    def __del__(self):
        if hasattr(self, 'client'):
            self.client.close()

    def _fetch_json(self, url: str) -> Optional[dict]:
        """Fetch JSON from Reddit."""
        try:
            resp = self.client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _post_to_content(self, post_data: dict) -> ScrapedContent:
        """Convert Reddit post JSON to ScrapedContent."""
        data = post_data["data"]

        # Combine title and body
        text_parts = [data.get("title", "")]
        if data.get("selftext"):
            text_parts.append(data["selftext"])

        raw_text = "\n\n".join(text_parts)

        return ScrapedContent(
            source_type=SourceType.REDDIT,
            source_url=f"https://reddit.com{data.get('permalink', '')}",
            source_id=data.get("id", ""),
            title=data.get("title", ""),
            raw_text=raw_text,
            author=data.get("author", "[deleted]"),
            posted_at=datetime.fromtimestamp(data.get("created_utc", 0)),
            subreddit=data.get("subreddit", ""),
            reddit_score=data.get("score", 0),
            reddit_num_comments=data.get("num_comments", 0),
        )

    def _fetch_comments(self, permalink: str, limit: int = 5) -> List[str]:
        """Fetch top comments for a post."""
        url = f"{BASE_URL}{permalink}.json?limit={limit}"
        data = self._fetch_json(url)

        if not data or len(data) < 2:
            return []

        comments = []
        try:
            comment_listing = data[1]["data"]["children"]
            for comment in comment_listing[:limit]:
                if comment["kind"] == "t1":  # t1 = comment
                    body = comment["data"].get("body", "")
                    if len(body) > 20:
                        comments.append(body)
        except (KeyError, IndexError) as e:
            logger.debug(f"Error parsing comments: {e}")

        return comments

    def _is_food_related(self, post_data: dict) -> bool:
        """Check if a post is food/restaurant related."""
        data = post_data["data"]
        text = f"{data.get('title', '')} {data.get('selftext', '')}".lower()

        food_indicators = [
            "restaurant", "food", "eat", "dining", "brunch", "lunch", "dinner",
            "cafe", "bistro", "bar", "pub", "takeout", "delivery",
            "ramen", "sushi", "pizza", "burger", "taco", "pho", "curry",
            "best place", "recommend", "where to", "hidden gem", "date night",
        ]

        return any(indicator in text for indicator in food_indicators)

    def scrape_subreddit(
        self,
        subreddit_name: str,
        time_filter: str = "month",
        limit: int = 50,
        include_comments: bool = False,
    ) -> List[ScrapedContent]:
        """
        Scrape a subreddit for food-related posts.

        Args:
            subreddit_name: Name of the subreddit
            time_filter: 'hour', 'day', 'week', 'month', 'year', 'all'
            limit: Maximum number of posts to fetch
            include_comments: Whether to fetch top comments (slower)

        Returns:
            List of ScrapedContent objects
        """
        results = []
        seen_ids = set()

        # Get top posts
        url = f"{BASE_URL}/r/{subreddit_name}/top.json?t={time_filter}&limit={limit}"
        data = self._fetch_json(url)

        if data and "data" in data:
            for post in data["data"]["children"]:
                if post["kind"] != "t3":  # t3 = post
                    continue

                post_id = post["data"].get("id")
                if post_id in seen_ids:
                    continue

                if self._is_food_related(post):
                    content = self._post_to_content(post)

                    # Optionally fetch comments
                    if include_comments:
                        comments = self._fetch_comments(post["data"]["permalink"])
                        if comments:
                            content.raw_text += "\n\n--- Top Comments ---\n" + "\n\n".join(comments)

                    results.append(content)
                    seen_ids.add(post_id)
                    logger.debug(f"Found: {post['data']['title'][:60]}...")

        # Search for food-related posts
        for keyword in FOOD_KEYWORDS[:5]:  # Limit to prevent rate limiting
            search_url = f"{BASE_URL}/r/{subreddit_name}/search.json?q={keyword}&restrict_sr=on&sort=top&t={time_filter}&limit=20"
            search_data = self._fetch_json(search_url)

            if search_data and "data" in search_data:
                for post in search_data["data"]["children"]:
                    if post["kind"] != "t3":
                        continue

                    post_id = post["data"].get("id")
                    if post_id in seen_ids:
                        continue

                    if self._is_food_related(post):
                        content = self._post_to_content(post)
                        results.append(content)
                        seen_ids.add(post_id)

        logger.info(f"Scraped {len(results)} posts from r/{subreddit_name}")
        return results

    def scrape_all_toronto(
        self,
        time_filter: str = "month",
        limit_per_sub: int = 50,
        include_comments: bool = False,
    ) -> List[ScrapedContent]:
        """
        Scrape all Toronto food subreddits.

        Args:
            time_filter: Time filter for posts
            limit_per_sub: Max posts per subreddit
            include_comments: Whether to fetch comments

        Returns:
            Combined list of scraped content
        """
        all_content = []
        seen_ids = set()

        for subreddit in TORONTO_SUBREDDITS:
            try:
                content = self.scrape_subreddit(
                    subreddit_name=subreddit,
                    time_filter=time_filter,
                    limit=limit_per_sub,
                    include_comments=include_comments,
                )

                # Deduplicate
                for item in content:
                    if item.source_id not in seen_ids:
                        seen_ids.add(item.source_id)
                        all_content.append(item)

            except Exception as e:
                logger.error(f"Error scraping r/{subreddit}: {e}")
                continue

        logger.info(f"Total scraped from Reddit: {len(all_content)} unique posts")
        return all_content

    def search_restaurant(
        self,
        restaurant_name: str,
        limit: int = 20,
    ) -> List[ScrapedContent]:
        """
        Search Reddit for mentions of a specific restaurant.

        Args:
            restaurant_name: Name of restaurant to search for
            limit: Max results

        Returns:
            List of mentions
        """
        results = []
        seen_ids = set()

        for subreddit in TORONTO_SUBREDDITS[:2]:
            url = f"{BASE_URL}/r/{subreddit}/search.json?q={restaurant_name}&restrict_sr=on&sort=relevance&limit={limit}"
            data = self._fetch_json(url)

            if data and "data" in data:
                for post in data["data"]["children"]:
                    if post["kind"] != "t3":
                        continue

                    post_id = post["data"].get("id")
                    if post_id not in seen_ids:
                        content = self._post_to_content(post)
                        results.append(content)
                        seen_ids.add(post_id)

        return results


# =============================================================================
# CLI for testing
# =============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    scraper = RedditScraper()

    # Test scrape from FoodToronto
    print("\n=== Testing r/FoodToronto ===")
    content = scraper.scrape_subreddit("FoodToronto", time_filter="month", limit=10)
    for item in content[:3]:
        print(f"\n--- {item.title} ---")
        print(f"Score: {item.reddit_score}, Comments: {item.reddit_num_comments}")
        print(f"URL: {item.source_url}")
        print(f"Text preview: {item.raw_text[:200]}...")

    # Test scrape from askTO
    print("\n=== Testing r/askTO ===")
    content = scraper.scrape_subreddit("askTO", time_filter="week", limit=10)
    for item in content[:3]:
        print(f"\n--- {item.title} ---")
        print(f"Score: {item.reddit_score}, Comments: {item.reddit_num_comments}")
        print(f"Text preview: {item.raw_text[:200]}...")
