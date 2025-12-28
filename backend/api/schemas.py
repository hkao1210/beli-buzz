"""
Pydantic schemas for Belly-Buzz API.
Re-exports from shared.models for backwards compatibility.
"""

from shared.models import (
    # API Response Models
    Restaurant as RestaurantDB,
    RestaurantResponse as Restaurant,
    SearchResponse,
    Review,

    # Extraction Models
    ExtractedRestaurant,
    SentimentAnalysis,
    ExtractionResult,

    # Social Models
    SocialMention,
    ScrapedContent,

    # Enums
    SourceType,
    SentimentLabel,
)

# Legacy schema aliases for backwards compatibility
RestaurantCreate = ExtractedRestaurant

# Additional schemas specific to API layer
from typing import List, Optional
from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    """Semantic search request."""
    q: str = Field(..., description="Natural language query")
    price_min: Optional[int] = Field(default=None, ge=1, le=4)
    price_max: Optional[int] = Field(default=None, ge=1, le=4)
    cuisine: Optional[List[str]] = Field(default=None)
    sort_by: Optional[str] = Field(default="buzz_score")
    sort_order: Optional[str] = Field(default="desc")
    limit: int = Field(default=20, ge=1, le=100)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    message: str
    supabase_connected: bool
