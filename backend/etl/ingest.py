import re
import logging
from typing import Optional, Dict

from dotenv import load_dotenv
from etl.db import get_supabase
from shared.models import (
    Restaurant,
    RestaurantMetrics,
    SocialMention,
)
from shared.embeddings.embeddings import get_embedding_service
from .scrapers.content import ContentScraper
from .llm.extractor import RestaurantExtractor
from .enrichment import GooglePlacesEnricher
from .scoring import calculate_metrics

load_dotenv()
logger = logging.getLogger(__name__)

# =============================================================================
# HELPERS
# =============================================================================

def create_slug(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-")

def price_hint_to_tier(price_hint: Optional[str], google_price: Optional[int]) -> int:
    """Restored price tier logic to fix missing argument issues."""
    if google_price:
        return min(max(google_price, 1), 4)
    if not price_hint:
        return 2
    hint = price_hint.lower()
    if any(k in hint for k in ["$$$$", "expensive", "pricey"]): return 4
    if any(k in hint for k in ["$$$", "upscale"]): return 3
    if any(k in hint for k in ["$$", "moderate"]): return 2
    return 1

def upsert_restaurant_core(supabase, restaurant: Restaurant) -> Optional[str]:
    """Upserts identity and returns UUID."""
    data = restaurant.model_dump(exclude={"id"})
    # Ensure embedding is handled by pgvector
    res = (
        supabase
        .table("restaurants")
        .upsert(data, on_conflict="google_place_id")
        .select("id")
        .execute()
    )
    rid = res.data[0]["id"] if res.data else None
    logger.info(f"Upserted restaurant {restaurant.name}: id={rid}, rows={len(res.data)}")
    return rid

def upsert_metrics(supabase, metrics: RestaurantMetrics):
    """Saves buzz/sentiment scores."""
    data = metrics.model_dump()
    res = supabase.table("restaurant_metrics").upsert(data, on_conflict="restaurant_id").execute()
    logger.info(f"Upserted metrics for {metrics.restaurant_id}: buzz={metrics.buzz_score}")

def upsert_mention(supabase, mention: SocialMention, restaurant_id: str):
    """Saves social proof linked to restaurant."""
    data = mention.model_dump(exclude={"id"})
    data["restaurant_id"] = restaurant_id
    # Ensure Enum to String conversion
    data["source_type"] = data["source_type"].value if hasattr(data["source_type"], "value") else data["source_type"]
    res = supabase.table("social_mentions").upsert(data, on_conflict="source_url").execute()
    logger.info(f"Upserted mention {mention.source_url[:50]} for restaurant {restaurant_id}")

# =============================================================================
# MAIN PIPELINE
# =============================================================================

async def run_pipeline(limit: int = 50):
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    supabase = get_supabase()
    scraper = ContentScraper()
    extractor = RestaurantExtractor()
    enricher = GooglePlacesEnricher()
    embedder = get_embedding_service()
    embedder.load()

    raw_content = scraper.scrape_all(blog_limit=limit)
    logger.info(f"Scraped {len(raw_content)} items")
    queue: Dict[str, Dict] = {}

    for item in raw_content:
        extracted_list, sentiment = extractor.process_content(item)
        for ext in extracted_list:
            logger.info(f"Looking up place: {ext.name}")
            place = enricher.find_place(ext.name)
            logger.info(f"Place lookup done for {ext.name}: {place.place_id if place else 'None'}")
            
            # Use place_id as key if available, else restaurant name
            key = place.place_id if place else ext.name
            
            # Skip if already in queue (dedup)
            if key in queue:
                logger.info(f"Skipping duplicate: {key}")
                continue
            
            if key not in queue:
                queue[key] = {"ext": ext, "place": place, "mentions": []}
            
            # Convert ScrapedContent to SocialMention
            mention = SocialMention(
                restaurant_name=ext.name,
                source_type=item.source_type,
                source_url=item.source_url,
                title=item.title,
                raw_text=item.raw_text[:3000],
                reddit_score=item.reddit_score,
                reddit_num_comments=item.reddit_num_comments,
                posted_at=item.posted_at,
                sentiment_score=sentiment.overall_score if sentiment else 0.0,
                sentiment_label=sentiment.label if sentiment else None,
                vibe_extracted=ext.vibe,
                dishes_mentioned=ext.recommended_dishes or []
            )
            queue[key]["mentions"].append(mention)

    logger.info(f"Processing {len(queue)} unique restaurant(s)")
    for key, data in queue.items():
        try:
            ext, place, mentions = data["ext"], data["place"], data["mentions"]
            logger.info(f"Processing {ext.name} ({key}): {len(mentions)} mentions")
            
            buzz, sentiment = calculate_metrics(mentions)

            restaurant = Restaurant(
                name=place.name if place else ext.name,
                slug=create_slug(place.name if place else ext.name),
                address=place.address if place else "Toronto",
                latitude=place.latitude if place else 0.0,
                longitude=place.longitude if place else 0.0,
                price_tier=price_hint_to_tier(ext.price_hint, place.price_level if place else None),
                google_place_id=place.place_id if place else None,
                google_maps_url=place.google_maps_url if place else None,
                vibe=ext.vibe,
                cuisine_tags=ext.cuisine_tags,
                embedding=embedder.embed_text(f"{ext.name} {ext.vibe}")
            )

            if supabase:
                logger.info(f"Upserting restaurant {restaurant.name}...")
                res_id = upsert_restaurant_core(supabase, restaurant)
                if res_id:
                    logger.info(f"Upserted restaurant with ID {res_id}, inserting metrics and mentions...")
                    upsert_metrics(supabase, RestaurantMetrics(
                        restaurant_id=res_id, buzz_score=buzz, sentiment_score=sentiment,
                        total_mentions=len(mentions), is_trending=(len(mentions) >= 2)
                    ))
                    for m in mentions: upsert_mention(supabase, m, res_id)
                    logger.info(f"Successfully inserted {len(mentions)} mentions for {restaurant.name}")
                else:
                    logger.warning(f"Failed to upsert restaurant {restaurant.name} (no ID returned)")
            else:
                logger.warning(f"Supabase client is None, skipping insert for {restaurant.name}")
        except Exception as e:
            logger.error(f"Failed to process {key}: {e}", exc_info=True)
