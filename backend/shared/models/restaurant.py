from typing import List, Optional
from pydantic import BaseModel, Field

class Restaurant(BaseModel):
    """Core Identity with Google Identifiers."""
    id: Optional[str] = None
    name: str
    slug: Optional[str] = None
    address: str
    city: str = "Toronto"
    latitude: float = 0.0
    longitude: float = 0.0
    price_tier: int = Field(2, ge=1, le=4)
    vibe: Optional[str] = None
    
    # Essential Google Info
    google_place_id: Optional[str] = None
    google_maps_url: Optional[str] = None
    
    embedding: Optional[List[float]] = None