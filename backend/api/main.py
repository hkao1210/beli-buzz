"""
Belly-Buzz FastAPI Backend
==========================
Real-time API for restaurant search and discovery.

Features:
- Semantic search with OpenAI embeddings + pgvector
- Filtering by price, cuisine
- Sorting by buzz score, sentiment, rating
- Trending restaurants endpoint
"""

import os
from typing import List, Optional
from contextlib import asynccontextmanager
from enum import Enum

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from dotenv import load_dotenv

from shared.models import RestaurantResponse, SearchResponse, Review
from embeddings import EmbeddingService, get_embedding_service
from db import set_supabase_client

load_dotenv()

# =============================================================================
# CONFIG
# =============================================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
CITY = os.getenv("CITY", "Toronto")

# Global instances
embedding_service: EmbeddingService = get_embedding_service()
supabase_client: Optional[Client] = None


# =============================================================================
# ENUMS FOR API
# =============================================================================

class SortBy(str, Enum):
    BUZZ = "buzz_score"
    SENTIMENT = "sentiment_score"
    VIRAL = "viral_score"
    RATING = "rating"
    PRICE = "price_tier"
    NAME = "name"
    MENTIONS = "total_mentions"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


# =============================================================================
# STARTUP / SHUTDOWN
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    if SUPABASE_URL and SUPABASE_SECRET_KEY:
        client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
        set_supabase_client(client)  # Share globally
        print("Supabase client initialized!")
    else:
        print("Warning: Supabase credentials not set")

    print("Belly-Buzz API ready!")
    yield
    print("Shutting down...")

# =============================================================================
# APP
# =============================================================================

app = FastAPI(
    title="Belly-Buzz API",
    description="AI-powered restaurant discovery with semantic search for Toronto",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def embed_query(query: str) -> List[float]:
    """Create embedding vector from search query."""
    if not embedding_service:
        raise HTTPException(status_code=500, detail="Embedding service not loaded")
    return embedding_service.embed_query(query)


async def search_supabase(
    query_embedding: Optional[List[float]] = None,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    cuisine: Optional[List[str]] = None,
    sort_by: SortBy = SortBy.BUZZ,
    sort_order: SortOrder = SortOrder.DESC,
    limit: int = 20,
) -> List[dict]:
    """Perform search in Supabase."""
    if not supabase_client:
        return []

    try:
        # If we have a query embedding, use vector search
        if query_embedding:
            result = supabase_client.rpc(
                "search_restaurants",
                {
                    "query_embedding": query_embedding,
                    "match_count": limit,
                    "price_min": price_min,
                    "price_max": price_max,
                    "filter_city": CITY,
                }
            ).execute()
            return result.data or []

        # Otherwise, do a standard query with filters
        query = supabase_client.table("restaurants").select("*")

        # Apply filters
        query = query.eq("city", CITY)

        if price_min:
            query = query.gte("price_tier", price_min)
        if price_max:
            query = query.lte("price_tier", price_max)
        if cuisine:
            # Filter by cuisine tags (any match)
            query = query.contains("cuisine_tags", cuisine)
        
        # Apply sorting
        sort_column = sort_by.value
        if sort_by == SortBy.RATING:
            sort_column = "google_rating"
        
        ascending = sort_order == SortOrder.ASC
        query = query.order(sort_column, desc=not ascending)
        
        query = query.limit(limit)
        
        result = query.execute()
        return result.data or []
        
    except Exception as e:
        print(f"Supabase search error: {e}")
        return []


def db_row_to_response(row: dict) -> RestaurantResponse:
    """Convert database row to API response."""
    return RestaurantResponse(
        id=str(row["id"]),
        name=row["name"],
        slug=row.get("slug"),
        address=row.get("address", ""),
        latitude=row.get("latitude", 0),
        longitude=row.get("longitude", 0),
        google_place_id=row.get("google_place_id"),
        google_maps_url=row.get("google_maps_url"),
        price_tier=row.get("price_tier", 2),
        rating=row.get("google_rating") or row.get("rating") or 0,
        photo_url=row.get("photo_url"),
        cuisine_tags=row.get("cuisine_tags", []),
        vibe=row.get("vibe"),
        review=Review(
            summary=row.get("vibe", ""),
            recommended_dishes=row.get("recommended_dishes", []),
            source_url=row.get("source_urls", [None])[0] if row.get("source_urls") else None,
            source_type=row.get("sources", [None])[0] if row.get("sources") else None,
        ) if row.get("vibe") else None,
        buzz_score=row.get("buzz_score", 0),
        sentiment_score=row.get("sentiment_score", 0),
        viral_score=row.get("viral_score", 0),
        total_mentions=row.get("total_mentions", 0),
        sources=row.get("sources", []),
        is_new=row.get("is_new", False),
        is_trending=row.get("is_trending", False),
    )

# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": f"Belly-Buzz API v2.0 - {CITY}",
        "supabase_connected": supabase_client is not None,
    }


@app.get("/search", response_model=SearchResponse)
async def search_restaurants(
    q: Optional[str] = Query(default=None, description="Natural language search query"),
    price_min: Optional[int] = Query(default=None, ge=1, le=4),
    price_max: Optional[int] = Query(default=None, ge=1, le=4),
    cuisine: Optional[List[str]] = Query(default=None),
    sort_by: SortBy = Query(default=SortBy.BUZZ, description="Sort field"),
    sort_order: SortOrder = Query(default=SortOrder.DESC, description="Sort order"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Search restaurants with semantic similarity and filters.

    Examples:
    - "romantic Italian date spot"
    - "cheap late night tacos"
    - "best ramen in Toronto"
    """
    # If Supabase is connected, use database
    if supabase_client:
        # Create embedding for semantic search
        query_embedding = embed_query(q) if q else None

        raw_results = await search_supabase(
            query_embedding=query_embedding,
            price_min=price_min,
            price_max=price_max,
            cuisine=cuisine,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
        )

        results = [db_row_to_response(row) for row in raw_results]

        return SearchResponse(
            results=results,
            total=len(results),
            query=q,
            filters={
                "price_min": price_min,
                "price_max": price_max,
                "cuisine": cuisine,
                "sort_by": sort_by.value,
                "sort_order": sort_order.value,
            }
        )

    # Fallback to mock data
    results = filter_mock_data(q, price_min, price_max, cuisine, sort_by, sort_order)

    return SearchResponse(
        results=results[:limit],
        total=len(results),
        query=q or "",
        filters={
            "price_min": price_min,
            "price_max": price_max,
            "cuisine": cuisine,
            "sort_by": sort_by.value,
            "sort_order": sort_order.value,
        }
    )


@app.get("/restaurants/{restaurant_id}", response_model=RestaurantResponse)
async def get_restaurant(restaurant_id: str):
    """Get a single restaurant by ID or slug."""
    # Try Supabase first
    if supabase_client:
        try:
            # Try by ID first
            result = supabase_client.table("restaurants").select("*").eq("id", restaurant_id).execute()
            
            # If not found, try by slug
            if not result.data:
                result = supabase_client.table("restaurants").select("*").eq("slug", restaurant_id).execute()
            
            if result.data:
                return db_row_to_response(result.data[0])
        except Exception as e:
            print(f"Supabase fetch error: {e}")
    
    # Fallback to mock data
    for restaurant in MOCK_RESTAURANTS:
        if restaurant.id == restaurant_id or restaurant.slug == restaurant_id:
            return restaurant
    
    raise HTTPException(status_code=404, detail="Restaurant not found")


@app.get("/trending", response_model=List[RestaurantResponse])
async def get_trending_restaurants(
    limit: int = Query(default=10, ge=1, le=50),
):
    """Get trending restaurants sorted by buzz score."""
    if supabase_client:
        try:
            result = supabase_client.rpc(
                "get_trending_restaurants",
                {"filter_city": CITY, "match_count": limit}
            ).execute()
            
            return [db_row_to_response(row) for row in (result.data or [])]
        except Exception as e:
            print(f"Trending fetch error: {e}")
    
    # Fallback to mock data sorted by buzz score
    sorted_mock = sorted(MOCK_RESTAURANTS, key=lambda r: r.buzz_score, reverse=True)
    return sorted_mock[:limit]


@app.get("/trending-queries", response_model=List[str])
async def get_trending_queries():
    """Get trending search queries."""
    return [
        "Best ramen in Toronto",
        "Romantic dinner Yorkville",
        "Late night tacos",
        "Cheap eats Kensington",
        "Brunch spots Queen West",
        "Best Thai food",
        "Hidden gem restaurants",
        "Omakase experience",
    ]


@app.get("/cuisines", response_model=List[str])
async def get_cuisines():
    """Get list of available cuisine types."""
    if supabase_client:
        try:
            result = supabase_client.table("restaurants").select("cuisine_tags").eq("city", CITY).execute()
            cuisines = set()
            for r in result.data:
                for tag in r.get("cuisine_tags", []):
                    cuisines.add(tag)
            return sorted(list(cuisines))
        except Exception as e:
            print(f"Cuisines fetch error: {e}")
    
    # Fallback
    return [
        "Baja-style",
        "Curry",
        "Fusion",
        "Halal",
        "Indian",
        "Italian",
        "Japanese",
        "Korean",
        "Mexican",
        "Neapolitan",
        "Noodles",
        "Omakase",
        "Pakistani",
        "Pizza",
        "Ramen",
        "Sandwiches",
        "Seafood",
        "Southeast Asian",
        "Street Food",
        "Sushi",
        "Tacos",
        "Thai",
        "Vietnamese",
    ]
