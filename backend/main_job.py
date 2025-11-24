"""Daily job orchestrator for the Beli Buzz MVP pipeline."""
from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Dict, List, Optional

try:  # Optional dependency during linting
    boto3 = import_module("boto3")
except ModuleNotFoundError:  # pragma: no cover
    boto3 = None  # type: ignore

try:
    googlemaps = import_module("googlemaps")
except ModuleNotFoundError:  # pragma: no cover
    googlemaps = None  # type: ignore

try:
    load_dotenv = import_module("dotenv").load_dotenv  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - optional
    def load_dotenv() -> bool:  # type: ignore[misc]
        return False

from analyzer_gemini import extract_restaurants
from scraper_reddit import get_reddit_posts
from scraper_web import fetch_curated_articles

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = Path(os.getenv("DATA_OUTPUT_PATH", REPO_ROOT / "frontend" / "public" / "data.json"))
CACHE_PATH = Path(os.getenv("GEOCODE_CACHE_PATH", Path(__file__).with_name("geocode_cache.json")))
GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
S3_KEY = os.getenv("S3_OBJECT_KEY", "latest.json")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DEFAULT_ANALYZER = os.getenv("ANALYZER_PROVIDER", "gemini")
USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "false").lower() == "true"


@dataclass
class ContentItem:
    content: str
    source: str
    meta: Dict[str, str] = field(default_factory=dict)


SAMPLE_POSTS = [
    ContentItem(
        content=(
            "Pai Northern Thai Kitchen just launched a khao soi special and the curry depth is unreal. "
            "Lineups still wrap around Duncan but worth it."
        ),
        source="mock:reddit",
        meta={"title": "Pai still slaps"},
    ),
    ContentItem(
        content=(
            "Seven Lives in Kensington is frying the crispiest Baja tacos and everyone on FoodToronto won't shut up about it."
        ),
        source="mock:reddit",
        meta={"title": "Seven Lives forever"},
    ),
    ContentItem(
        content=(
            "The Burger's Priest secret menu is back. Double-double with the Vatican-style bun might be peak comfort food right now."
        ),
        source="mock:article",
        meta={"title": "Burger wars"},
    ),
]


class GeocodeCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._data = self._load()

    def _load(self) -> Dict[str, dict]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except json.JSONDecodeError:
                logging.warning("Unable to parse cache file %s, starting fresh", self.path)
        return {}

    def get(self, name: str) -> Optional[dict]:
        return self._data.get(name.lower())

    def set(self, name: str, location: dict) -> None:
        self._data[name.lower()] = location

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))


def slugify(value: str) -> str:
    return "-".join(value.lower().split())


def collect_content(limit: int, max_articles: int, mock_data: bool) -> List[ContentItem]:
    if mock_data:
        logging.info("Using bundled mock content")
        return SAMPLE_POSTS

    items: List[ContentItem] = []

    reddit_posts = get_reddit_posts(limit=limit)
    for post in reddit_posts:
        combined = "\n".join(filter(None, [post.get("title", ""), post.get("text", "")] + post.get("comments", [])))
        if len(combined.strip()) < 40:
            continue
        items.append(ContentItem(content=combined, source="reddit", meta={"id": post.get("id", "n/a")}))

    articles = fetch_curated_articles(max_articles=max_articles)
    for article in articles:
        combined = f"{article['title']}\n{article.get('summary', '')}\n{article.get('url', '')}"
        items.append(ContentItem(content=combined, source=article.get("source", "article"), meta={"url": article.get("url", "")}))

    if not items:
        logging.warning("Scrapers returned no data; falling back to mock content")
        return SAMPLE_POSTS

    return items


def analyze_content(items: List[ContentItem], provider: str) -> Dict[str, dict]:
    restaurants: Dict[str, dict] = {}
    for item in items:
        extracted = extract_restaurants(item.content, provider)
        for match in extracted:
            name = match.get("name")
            if not name:
                continue
            record = restaurants.setdefault(
                name,
                {
                    "mentions": 0,
                    "total_sentiment": 0.0,
                    "summaries": [],
                    "sources": set(),
                },
            )
            record["mentions"] += 1
            record["total_sentiment"] += float(match.get("sentiment", 6))
            summary = match.get("summary") or item.meta.get("title", "")
            if summary:
                record["summaries"].append(summary)
            record["sources"].add(item.source)

    return restaurants


def geocode_restaurants(restaurant_map: Dict[str, dict]) -> List[dict]:
    cache = GeocodeCache(CACHE_PATH)
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_KEY) if googlemaps and GOOGLE_MAPS_KEY else None
    final: List[dict] = []

    for name, data in restaurant_map.items():
        if data["mentions"] == 0:
            continue
        avg_sentiment = data["total_sentiment"] / data["mentions"]
        location = cache.get(name)
        if not location and gmaps:
            try:
                result = gmaps.places(query=f"{name} Toronto")
                if result["status"] == "OK" and result["results"]:
                    loc = result["results"][0]["geometry"]["location"]
                    location = {
                        "lat": loc["lat"],
                        "lng": loc["lng"],
                        "address": result["results"][0].get("formatted_address"),
                    }
                    cache.set(name, location)
            except Exception as exc:  # pragma: no cover - network variability
                logging.warning("Geocoding failed for %s: %s", name, exc)

        final.append(
            {
                "id": slugify(name),
                "name": name,
                "buzz_score": round(data["mentions"] + avg_sentiment, 2),
                "sentiment": round(avg_sentiment, 1),
                "mentions": data["mentions"],
                "summary": data["summaries"][0] if data["summaries"] else "Trending on Toronto food feeds",
                "location": location,
                "sources": sorted(data["sources"]),
            }
        )

    cache.save()
    final.sort(key=lambda entry: entry["buzz_score"], reverse=True)
    return final


def upload_to_s3(file_path: Path) -> bool:
    if not S3_BUCKET:
        logging.info("S3 bucket not configured; skipping upload")
        return False
    if boto3 is None:
        logging.warning("boto3 missing; cannot upload to S3")
        return False
    client = boto3.client("s3", region_name=AWS_REGION)
    extra_args = {"ContentType": "application/json", "ACL": "public-read"}
    client.upload_file(str(file_path), S3_BUCKET, S3_KEY, ExtraArgs=extra_args)
    logging.info("Uploaded %s to s3://%s/%s", file_path, S3_BUCKET, S3_KEY)
    return True


def write_payload(payload: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    logging.info("Saved %s", output_path)
    return output_path


def run_daily_job(args: argparse.Namespace) -> Path:
    content_items = collect_content(limit=args.limit, max_articles=args.max_articles, mock_data=args.mock_data)
    restaurant_map = analyze_content(content_items, provider=args.analyzer)

    if not restaurant_map:
        logging.warning("Analyzer returned zero restaurants; injecting mock payload")
        restaurant_map = analyze_content(SAMPLE_POSTS, provider="gemini")

    restaurants = geocode_restaurants(restaurant_map)
    payload = {
        "date": datetime.utcnow().isoformat(),
        "restaurants": restaurants,
    }

    output_file = write_payload(payload, args.output)
    if args.upload:
        upload_to_s3(output_file)
    return output_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Beli Buzz daily scraping job")
    parser.add_argument("--limit", type=int, default=20, help="Max Reddit posts to inspect")
    parser.add_argument("--max-articles", type=int, default=8, help="Max curated articles to ingest")
    parser.add_argument("--mock-data", action="store_true", default=USE_MOCK_DATA, help="Use bundled mock fixtures")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Where to save trending JSON")
    parser.add_argument(
        "--analyzer",
        type=str,
        default=DEFAULT_ANALYZER,
        choices=["gemini", "huggingface"],
        help="LLM provider to extract restaurants",
    )
    parser.add_argument("--upload", action="store_true", help="Upload the artifact to S3")
    parser.add_argument("--log-level", type=str, default="INFO", help="Logging level")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")
    output_file = run_daily_job(args)
    logging.info("Daily job complete: %s", output_file)


if __name__ == "__main__":
    main()
