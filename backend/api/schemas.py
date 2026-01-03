from typing import List, Optional
from pydantic import BaseModel

class Review(BaseModel):
    summary: str
    recommended_dishes: List[str]

class RestaurantResponse(BaseModel):
    """The de-bloated response for the UI."""
    id: str
    name: str
    slug: Optional[str]
    address: str
    latitude: float
    longitude: float
    google_maps_url: Optional[str]
    price_tier: int
    vibe: Optional[str]
    cuisine_tags: List[str]
    buzz_score: float
    sentiment_score: float
    total_mentions: int
    is_trending: bool
    review: Optional[Review] = None

class SearchResponse(BaseModel):
    results: List[RestaurantResponse]
    total: int
    query: str
