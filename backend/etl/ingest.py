"""
Belly-Buzz Ingestion Pipeline (The "Night Shift")
=================================================
Complete ETL pipeline for restaurant data.

Refactored for Normalized Schema:
- Core Restaurant Identity (Table: restaurants)
- High-Frequency Metrics (Table: restaurant_metrics)
- Social Proof (Table: social_mentions)
"""

import os
import re
import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

from dotenv import load_dotenv
from db import get_supabase
from shared.models import (
    Restaurant,
    RestaurantMetrics,
    SocialMention,
    ScrapedContent,
    ExtractedRestaurant,
    SourceType,
)
from embeddings import get_embedding_service
from .scrapers.content import ContentScraper
from .llm.extractor import RestaurantExtractor
from .enrichment import GooglePlacesEnricher
from .scoring import calculate_metrics

load_dotenv()

# =============================================================================
# CONFIG & LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# PIPELINE STATS
# =============================================================================

@dataclass
class PipelineStats:
    scraped: int = 0
    extracted_restaurants: int = 0
    enriched: int = 0
    stored: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)

    def summary(self) -> str:
        elapsed = datetime.now() - self.start_time
        return (
            f"\n{'='*50}\nPipeline Complete!\n{'='*50}\n"
            f"Duration: {elapsed.total_seconds():.1f}s\n"
            f"Items gathered: {self.scraped}\n"
            f"Restaurants found: {self.extracted_restaurants}\n"
            f"Google matches: {self.enriched}\n"
            f"Database updates: {self.stored}\n"
            f"Errors encountered: {len(self.errors)}\n"
        )

# =============================================================================
# HELPERS
# =============================================================================

def create_slug(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")

# =============================================================================
# DATABASE OPERATIONS (Normalized)
# =============================================================================

def upsert_restaurant(supabase: Client, restaurant: Restaurant) -> Optional[str]:
    """Upserts core restaurant data and returns the UUID."""
    try:
        data = {
            "name": restaurant.name,
            "slug": restaurant.slug or create_slug(restaurant.name),
            "address": restaurant.address,
            "city": restaurant.city,
            "latitude": restaurant.latitude,
            "longitude": restaurant.longitude,
            "price_tier": restaurant.price_tier,
            "photo_url": restaurant.photo_url,
            "vibe": restaurant.vibe,
            "google_place_id": restaurant.google_place_id,
            "google_maps_url": restaurant.google_maps_url,
            "embedding": restaurant.embedding,
        }
        # Clean None values
        data = {k: v for k, v in data.items() if v is not None}

        # Use google_place_id as the unique constraint for matching
        result = supabase.table("restaurants").upsert(
            data, on_conflict="google_place_id"
        ).execute()
        
        return result.data[0]["id"] if result.data else None
    except Exception as e:
        logger.error(f"Failed to upsert restaurant {restaurant.name}: {e}")
        return None

def upsert_metrics(supabase: Client, metrics: RestaurantMetrics):
    """Upserts the scores into the metrics table."""
    try:
        data = metrics.model_dump()
        data["last_updated_at"] = datetime.now().isoformat()
        supabase.table("restaurant_metrics").upsert(data, on_conflict="restaurant_id").execute()
    except Exception as e:
        logger.error(f"Failed to upsert metrics for {metrics.restaurant_id}: {e}")

def upsert_mention(supabase: Client, mention: SocialMention, restaurant_id: str):
    """Saves the raw social proof."""
    try:
        data = mention.model_dump()
        data["restaurant_id"] = restaurant_id
        # Convert enums to string values
        data["source_type"] = data["source_type"].value if hasattr(data["source_type"], "value") else data["source_type"]
        data["posted_at"] = data["posted_at"].isoformat() if data["posted_at"] else None
        data["scraped_at"] = datetime.now().isoformat()
        
        supabase.table("social_mentions").upsert(data, on_conflict="source_url").execute()
    except Exception as e:
        logger.error(f"Failed to upsert mention {mention.source_url}: {e}")

# =============================================================================
# MAIN PIPELINE
# =============================================================================

async def run_pipeline(limit: int = 50, days_back: int = 7):
    stats = PipelineStats()
    logger.info(f"Starting ingestion for {CITY}")

    # Initialize Refactored Services
    supabase = get_supabase()
    scraper = ContentScraper()
    extractor = RestaurantExtractor()
    enricher = GooglePlacesEnricher()
    embedder = get_embedding_service()
    embedder.load() # Pre-warm OpenAI client

    # 1. SCRAPE: Unified Blog + Reddit engine
    raw_content = scraper.scrape_all(blog_limit=limit, reddit_limit=limit, days_back=days_back, fetch_full_text=True)
    stats.scraped = len(raw_content)

    if not raw_content:
        logger.warning("No new content found.")
        return stats

    # 2. EXTRACT & GROUP: Use LLM and Google to group mentions by official Place ID
    # This prevents the "God Object" bloat and duplicate entries
    processing_queue: Dict[str, Dict] = {}

    logger.info("Step 2: Extracting and grouping mentions...")
    for item in raw_content:
        try:
            extracted_list, _ = extractor.process_content(item)
            for ext in extracted_list:
                # One-time Google lookup for ID/Address
                place = enricher.find_place(ext.name, city=CITY)
                key = place.place_id if place else ext.name # Fallback to name if not in Google
                
                if key not in processing_queue:
                    processing_queue[key] = {
                        "ext": ext,
                        "place": place,
                        "mentions": []
                    }
                
                # Map ScrapedContent to SocialMention model
                mention = SocialMention(
                    restaurant_id="", # Placeholder, filled after restaurant upsert
                    source_type=item.source_type,
                    source_url=item.source_url,
                    title=item.title,
                    raw_text=item.raw_text[:5000],
                    reddit_score=item.reddit_score,
                    reddit_num_comments=item.reddit_num_comments,
                    sentiment_score=0.0, # Filled by scoring engine
                    posted_at=item.posted_at
                )
                processing_queue[key]["mentions"].append(mention)
        except Exception as e:
            stats.errors.append(f"Extraction error: {str(e)[:50]}")

    stats.extracted_restaurants = len(processing_queue)

    # 3. ENRICH, EMBED, SCORE, STORE
    logger.info(f"Step 3: Finalizing {len(processing_queue)} restaurants...")
    for key, data in processing_queue.items():
        try:
            ext = data["ext"]
            place = data["place"]
            mentions = data["mentions"]

            # Scoring: Simplified logic (Buzz + Sentiment)
            buzz, sentiment = calculate_metrics(mentions)
            for m in mentions: m.sentiment_score = sentiment # Backfill mention sentiment

            # Vectorization: Name + Extracted Vibe
            vector = embedder.embed_text(f"{place.name if place else ext.name} {ext.vibe}")

            # Object Construction (Core Identity)
            restaurant = Restaurant(
                name=place.name if place else ext.name,
                slug=create_slug(place.name if place else ext.name),
                address=place.address if place else "",
                latitude=place.latitude if place else 0.0,
                longitude=place.longitude if place else 0.0,
                photo_url=place.photo_url if place and hasattr(place, 'photo_url') else None,
                vibe=ext.vibe,
                google_place_id=place.place_id if place else None,
                google_maps_url=place.google_maps_url if place and hasattr(place, 'google_maps_url') else None,
                embedding=vector
            )

            if supabase:
                # A. Upsert Restaurant Core
                res_id = upsert_restaurant(supabase, restaurant)
                if res_id:
                    # B. Upsert Simplified Metrics
                    metrics = RestaurantMetrics(
                        restaurant_id=res_id,
                        buzz_score=buzz,
                        sentiment_score=sentiment,
                        total_mentions=len(mentions),
                        is_trending=(len(mentions) >= 2)
                    )
                    upsert_metrics(supabase, metrics)

                    # C. Store Mentions (Social Proof)
                    for m in mentions:
                        upsert_mention(supabase, m, res_id)
                    
                    stats.stored += 1
                    if place: stats.enriched += 1
            else:
                logger.info(f"[Dry Run] Processed {restaurant.name} (Buzz: {buzz})")

        except Exception as e:
            logger.error(f"Error finalizing {key}: {e}")
            stats.errors.append(f"Storage error: {str(e)[:50]}")

    return stats

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    results = asyncio.run(run_pipeline(limit=args.limit, days_back=args.days))
    print(results.summary())