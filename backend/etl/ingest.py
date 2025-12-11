"""
Belly-Buzz Ingestion Pipeline (The "Night Shift")
=================================================
Complete ETL pipeline for restaurant data.

Runs as a scheduled job (e.g., GitHub Actions cron).

Pipeline Steps:
1. SCRAPE: Ingest from Reddit (PRAW) and food blogs (Crawl4AI)
2. EXTRACT: LLM extracts restaurant entities and sentiment
3. ENRICH: Google Places API adds location data
4. VECTORIZE: Create embeddings for semantic search
5. SCORE: Calculate buzz, viral, and sentiment scores
6. STORE: Persist to Supabase (PostgreSQL + pgvector)
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from dotenv import load_dotenv
from supabase import create_client, Client

from models import (
    Restaurant,
    SocialMention,
    ScrapedContent,
    ExtractedRestaurant,
    GooglePlaceData,
    SourceType,
    SentimentLabel,
)
from embeddings import EmbeddingService
from .scrapers.reddit import RedditScraper
from .scrapers.blogs import BlogScraper
from .llm.extractor import RestaurantExtractor
from .enrichment import GooglePlacesEnricher
from .scoring import calculate_all_scores, update_restaurant_scores

load_dotenv()

# =============================================================================
# CONFIG
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Environment
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
CITY = os.getenv("CITY", "Toronto")


# =============================================================================
# DATABASE CLIENT
# =============================================================================

def get_supabase() -> Optional[Client]:
    """Get Supabase client."""
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        logger.warning("Supabase credentials not set")
        return None
    return create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)


# =============================================================================
# PIPELINE RESULT TRACKING
# =============================================================================

@dataclass
class PipelineStats:
    """Track pipeline execution stats."""
    scraped_reddit: int = 0
    scraped_blogs: int = 0
    extracted_restaurants: int = 0
    enriched: int = 0
    stored: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    
    def summary(self) -> str:
        elapsed = datetime.now() - self.start_time
        return (
            f"\n{'='*50}\n"
            f"Pipeline Complete!\n"
            f"{'='*50}\n"
            f"Duration: {elapsed.total_seconds():.1f}s\n"
            f"Reddit posts scraped: {self.scraped_reddit}\n"
            f"Blog pages scraped: {self.scraped_blogs}\n"
            f"Restaurants extracted: {self.extracted_restaurants}\n"
            f"Enriched with Google Places: {self.enriched}\n"
            f"Stored to database: {self.stored}\n"
            f"Errors: {len(self.errors)}\n"
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_slug(name: str) -> str:
    """Create URL-friendly slug from restaurant name."""
    import re
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def price_hint_to_tier(price_hint: Optional[str], google_price: Optional[int]) -> int:
    """Convert price hint to tier (1-4)."""
    if google_price:
        return min(max(google_price, 1), 4)
    
    if not price_hint:
        return 2
    
    hint = price_hint.lower()
    
    if "$$$$" in hint or "expensive" in hint or "splurge" in hint or "pricey" in hint:
        return 4
    elif "$$$" in hint or "upscale" in hint:
        return 3
    elif "$$" in hint or "moderate" in hint:
        return 2
    elif "$" in hint or "cheap" in hint or "affordable" in hint or "budget" in hint:
        return 1
    
    return 2


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def upsert_restaurant(
    supabase: Client,
    restaurant: Restaurant,
) -> bool:
    """Insert or update restaurant in database."""
    try:
        # Prepare data for insert
        data = {
            "name": restaurant.name,
            "slug": restaurant.slug or create_slug(restaurant.name),
            "address": restaurant.address,
            "city": restaurant.city,
            "latitude": restaurant.latitude,
            "longitude": restaurant.longitude,
            "google_place_id": restaurant.google_place_id,
            "google_maps_url": restaurant.google_maps_url,
            "google_rating": restaurant.google_rating,
            "google_reviews_count": restaurant.google_reviews_count,
            "price_tier": restaurant.price_tier,
            "photo_url": restaurant.photo_url,
            "cuisine_tags": restaurant.cuisine_tags,
            "vibe": restaurant.vibe,
            "recommended_dishes": restaurant.recommended_dishes,
            "buzz_score": restaurant.buzz_score,
            "sentiment_score": restaurant.sentiment_score,
            "viral_score": restaurant.viral_score,
            "pro_score": restaurant.pro_score,
            "total_mentions": restaurant.total_mentions,
            "is_new": restaurant.is_new,
            "is_trending": restaurant.is_trending,
            "sources": restaurant.sources,
            "source_urls": restaurant.source_urls,
            "embedding": restaurant.embedding,
            "last_scraped_at": datetime.now().isoformat(),
        }
        
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        
        # Upsert based on google_place_id if available, else name
        if restaurant.google_place_id:
            result = supabase.table("restaurants").upsert(
                data,
                on_conflict="google_place_id"
            ).execute()
        else:
            # Check if exists by name
            existing = supabase.table("restaurants").select("id").eq("name", restaurant.name).execute()
            if existing.data:
                result = supabase.table("restaurants").update(data).eq("name", restaurant.name).execute()
            else:
                result = supabase.table("restaurants").insert(data).execute()
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to upsert restaurant {restaurant.name}: {e}")
        return False


def upsert_mention(
    supabase: Client,
    mention: SocialMention,
    restaurant_id: Optional[str] = None,
) -> bool:
    """Insert or update social mention."""
    try:
        data = {
            "restaurant_id": restaurant_id,
            "restaurant_name": mention.restaurant_name,
            "source_type": mention.source_type.value if isinstance(mention.source_type, SourceType) else mention.source_type,
            "source_url": mention.source_url,
            "source_id": mention.source_id,
            "title": mention.title,
            "raw_text": mention.raw_text[:10000],  # Limit text size
            "subreddit": mention.subreddit,
            "reddit_score": mention.reddit_score,
            "reddit_num_comments": mention.reddit_num_comments,
            "author": mention.author,
            "sentiment_score": mention.sentiment_score,
            "sentiment_label": mention.sentiment_label.value if mention.sentiment_label else None,
            "aspects": mention.aspects,
            "dishes_mentioned": mention.dishes_mentioned,
            "price_mentioned": mention.price_mentioned,
            "vibe_extracted": mention.vibe_extracted,
            "engagement_score": mention.engagement_score,
            "posted_at": mention.posted_at.isoformat() if mention.posted_at else None,
            "scraped_at": datetime.now().isoformat(),
        }
        
        data = {k: v for k, v in data.items() if v is not None}
        
        result = supabase.table("social_mentions").upsert(
            data,
            on_conflict="source_url"
        ).execute()
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to upsert mention: {e}")
        return False


def get_mentions_for_restaurant(
    supabase: Client,
    restaurant_name: str,
) -> List[SocialMention]:
    """Get all mentions for a restaurant."""
    try:
        result = supabase.table("social_mentions").select("*").eq("restaurant_name", restaurant_name).execute()
        
        mentions = []
        for row in result.data:
            mention = SocialMention(
                restaurant_name=row["restaurant_name"],
                source_type=row["source_type"],
                source_url=row["source_url"],
                raw_text=row.get("raw_text", ""),
                reddit_score=row.get("reddit_score", 0),
                reddit_num_comments=row.get("reddit_num_comments", 0),
                sentiment_score=row.get("sentiment_score"),
                sentiment_label=SentimentLabel(row["sentiment_label"]) if row.get("sentiment_label") else None,
                posted_at=datetime.fromisoformat(row["posted_at"]) if row.get("posted_at") else None,
            )
            mentions.append(mention)
        
        return mentions
    except Exception as e:
        logger.error(f"Failed to get mentions for {restaurant_name}: {e}")
        return []


# =============================================================================
# MAIN PIPELINE
# =============================================================================

async def run_pipeline(
    scrape_reddit: bool = True,
    scrape_blogs: bool = True,
    time_filter: str = "month",
    limit_per_source: int = 50,
) -> PipelineStats:
    """
    Run the full ingestion pipeline.
    
    Args:
        scrape_reddit: Whether to scrape Reddit
        scrape_blogs: Whether to scrape blogs
        time_filter: Time filter for Reddit posts
        limit_per_source: Max items per source
        
    Returns:
        PipelineStats with execution summary
    """
    stats = PipelineStats()
    
    logger.info(f"Starting ingestion pipeline for {CITY}")
    logger.info(f"Reddit: {scrape_reddit}, Blogs: {scrape_blogs}")
    
    # Initialize services
    supabase = get_supabase()
    extractor = RestaurantExtractor()
    embedder = EmbeddingService()
    enricher = GooglePlacesEnricher()
    
    # Load embedding model
    embedder.load()
    
    all_content: List[ScrapedContent] = []
    
    # ==========================================================================
    # STEP 1: SCRAPE DATA
    # ==========================================================================
    
    if scrape_reddit:
        logger.info("Step 1a: Scraping Reddit...")
        reddit_scraper = RedditScraper()
        if reddit_scraper.reddit:
            reddit_content = reddit_scraper.scrape_all_toronto(
                time_filter=time_filter,
                limit_per_sub=limit_per_source,
            )
            all_content.extend(reddit_content)
            stats.scraped_reddit = len(reddit_content)
            logger.info(f"Scraped {len(reddit_content)} Reddit posts")
        else:
            logger.warning("Reddit scraper not available (check credentials)")
    
    if scrape_blogs:
        logger.info("Step 1b: Scraping blogs...")
        blog_scraper = BlogScraper()
        if blog_scraper.has_crawler:
            blog_content = await blog_scraper.scrape_all_blogs()
            all_content.extend(blog_content)
            stats.scraped_blogs = len(blog_content)
            logger.info(f"Scraped {len(blog_content)} blog pages")
        else:
            logger.warning("Blog scraper not available (install crawl4ai)")
    
    if not all_content:
        logger.warning("No content scraped, exiting")
        return stats
    
    # ==========================================================================
    # STEP 2: EXTRACT RESTAURANTS WITH LLM
    # ==========================================================================
    
    logger.info("Step 2: Extracting restaurants with LLM...")
    
    # Track all extracted restaurants and their mentions
    restaurant_mentions: Dict[str, List[SocialMention]] = {}
    restaurant_data: Dict[str, ExtractedRestaurant] = {}
    
    for content in all_content:
        try:
            restaurants, sentiment = extractor.process_content(content)
            
            for extracted in restaurants:
                # Create mention record
                mention = SocialMention(
                    restaurant_name=extracted.name,
                    source_type=content.source_type,
                    source_url=content.source_url,
                    source_id=content.source_id,
                    title=content.title,
                    raw_text=content.raw_text,
                    subreddit=content.subreddit,
                    reddit_score=content.reddit_score or 0,
                    reddit_num_comments=content.reddit_num_comments or 0,
                    author=content.author,
                    sentiment_score=sentiment.overall_score if sentiment else None,
                    sentiment_label=sentiment.label if sentiment else None,
                    aspects=sentiment.aspects if sentiment else None,
                    dishes_mentioned=extracted.recommended_dishes,
                    price_mentioned=extracted.price_hint,
                    vibe_extracted=extracted.vibe,
                    posted_at=content.posted_at,
                )
                
                # Group by restaurant
                if extracted.name not in restaurant_mentions:
                    restaurant_mentions[extracted.name] = []
                    restaurant_data[extracted.name] = extracted
                
                restaurant_mentions[extracted.name].append(mention)
                
        except Exception as e:
            logger.error(f"Error processing content: {e}")
            stats.errors.append(f"Extraction error: {str(e)[:100]}")
    
    stats.extracted_restaurants = len(restaurant_data)
    logger.info(f"Extracted {len(restaurant_data)} unique restaurants")
    
    # ==========================================================================
    # STEP 3-6: ENRICH, VECTORIZE, SCORE, AND STORE
    # ==========================================================================
    
    logger.info("Steps 3-6: Enriching, vectorizing, scoring, and storing...")
    
    for name, extracted in restaurant_data.items():
        try:
            mentions = restaurant_mentions[name]
            
            # Step 3: Enrich with Google Places
            place_data = enricher.find_place(name, city=CITY)
            if place_data:
                stats.enriched += 1
            
            # Step 4: Create embedding
            embedding = embedder.embed_extracted(extracted)
            
            # Merge all data into restaurant object
            restaurant = Restaurant(
                name=place_data.name if place_data else extracted.name,
                slug=create_slug(place_data.name if place_data else extracted.name),
                address=place_data.address if place_data else "",
                city=CITY,
                latitude=place_data.latitude if place_data else 0.0,
                longitude=place_data.longitude if place_data else 0.0,
                google_place_id=place_data.place_id if place_data else None,
                google_maps_url=place_data.google_maps_url if place_data else None,
                google_rating=place_data.rating if place_data else None,
                google_reviews_count=place_data.reviews_count if place_data else 0,
                price_tier=price_hint_to_tier(extracted.price_hint, place_data.price_level if place_data else None),
                photo_url=place_data.photo_url if place_data else None,
                cuisine_tags=extracted.cuisine_tags,
                vibe=extracted.vibe,
                recommended_dishes=extracted.recommended_dishes,
                sources=list(set(m.source_type.value if isinstance(m.source_type, SourceType) else m.source_type for m in mentions)),
                source_urls=list(set(m.source_url for m in mentions)),
                embedding=embedding,
            )
            
            # Step 5: Calculate scores
            restaurant = update_restaurant_scores(restaurant, mentions)
            
            # Step 6: Store to database
            if supabase:
                # Store restaurant
                if upsert_restaurant(supabase, restaurant):
                    stats.stored += 1
                    
                    # Get restaurant ID for mentions
                    result = supabase.table("restaurants").select("id").eq("name", restaurant.name).execute()
                    restaurant_id = result.data[0]["id"] if result.data else None
                    
                    # Store mentions
                    for mention in mentions:
                        upsert_mention(supabase, mention, restaurant_id)
            else:
                logger.info(f"Would store: {restaurant.name} (Buzz: {restaurant.buzz_score})")
                
        except Exception as e:
            logger.error(f"Error processing {name}: {e}")
            stats.errors.append(f"Processing {name}: {str(e)[:100]}")
    
    return stats


# =============================================================================
# CLI ENTRY POINTS
# =============================================================================

async def main():
    """Main entry point for the ingestion pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Beli-Buzz Ingestion Pipeline")
    parser.add_argument("--no-reddit", action="store_true", help="Skip Reddit scraping")
    parser.add_argument("--no-blogs", action="store_true", help="Skip blog scraping")
    parser.add_argument("--time-filter", default="month", choices=["hour", "day", "week", "month", "year", "all"])
    parser.add_argument("--limit", type=int, default=50, help="Max items per source")
    
    args = parser.parse_args()
    
    stats = await run_pipeline(
        scrape_reddit=not args.no_reddit,
        scrape_blogs=not args.no_blogs,
        time_filter=args.time_filter,
        limit_per_source=args.limit,
    )
    
    print(stats.summary())
    
    if stats.errors:
        print("\nErrors:")
        for error in stats.errors[:10]:
            print(f"  - {error}")


if __name__ == "__main__":
    asyncio.run(main())
