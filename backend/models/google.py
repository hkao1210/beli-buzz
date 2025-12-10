"""Google Places API models."""

from typing import List, Optional
from pydantic import BaseModel, Field


class GooglePlaceData(BaseModel):
    """Data enriched from Google Places API."""
    place_id: str
    name: str
    address: str
    neighborhood: Optional[str] = None
    city: str = "Toronto"
    latitude: float
    longitude: float
    price_level: Optional[int] = Field(None, ge=0, le=4)
    rating: Optional[float] = Field(None, ge=0, le=5)
    reviews_count: Optional[int] = None
    google_maps_url: str
    photo_reference: Optional[str] = None
    photo_url: Optional[str] = None
    types: List[str] = Field(default_factory=list)
