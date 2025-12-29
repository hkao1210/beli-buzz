"""
Google Places Enrichment (New Places V1 API)
============================================
Enriches restaurant data using the google-maps-places library.
"""

import os
import logging
from typing import Optional, List, Dict
from google.maps import places_v1
from pydantic import BaseModel
from dotenv import load_dotenv

from shared.models import ExtractedRestaurant

load_dotenv()
logger = logging.getLogger(__name__)

class GooglePlaceDTO(BaseModel):
    """Internal DTO for enrichment results."""
    place_id: str
    name: str
    address: str
    latitude: float
    longitude: float
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    price_level: Optional[int] = None
    google_maps_url: str
    photo_url: Optional[str] = None

class GooglePlacesEnricher:
    """Uses the modern google-maps-places client for restaurant enrichment."""
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.client = self._init_client()
        
    def _init_client(self) -> Optional[places_v1.PlacesClient]:
        if not self.api_key:
            logger.warning("GOOGLE_MAPS_API_KEY not set")
            return None
        try:
            return places_v1.PlacesClient(client_options={"api_key": self.api_key})
        except Exception as e:
            logger.error(f"Failed to initialize Places V1 client: {e}")
            return None

    def find_place(self, restaurant_name: str, city: str = "Toronto") -> Optional[GooglePlaceDTO]:
        """Finds a restaurant using the modern search_text (V1) method."""
        if not self.client: return None
        
        try:
            # The New API requires a Field Mask in the metadata for billing/performance
            field_mask = "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.priceLevel,places.googleMapsUri,places.photos"
            metadata = [("x-goog-fieldmask", field_mask)]

            # Request structure for the new SearchText endpoint
            request = {
                "text_query": f"{restaurant_name} {city}",
                "max_result_count": 1,
                "location_bias": {
                    "circle": {
                        "center": {"latitude": 43.6532, "longitude": -79.3832}, # Toronto
                        "radius": 10000.0
                    }
                }
            }

            response = self.client.search_text(request=request, metadata=metadata)
            
            if not response.places:
                logger.warning(f"No Google result for: {restaurant_name}")
                return None
            
            place = response.places[0]
            
            # Extract photo URL if available
            photo_url = None
            if place.photos:
                photo_name = place.photos[0].name # format: places/{id}/photos/{pid}
                photo_url = f"https://places.googleapis.com/v1/{photo_name}/media?maxHeightPx=400&maxWidthPx=400&key={self.api_key}"

            return GooglePlaceDTO(
                place_id=place.id,
                name=place.display_name.text if place.display_name else restaurant_name,
                address=place.formatted_address,
                latitude=place.location.latitude,
                longitude=place.location.longitude,
                rating=place.rating,
                reviews_count=place.user_rating_count,
                price_level=int(place.price_level) if place.price_level else None,
                google_maps_url=place.google_maps_uri,
                photo_url=photo_url
            )
            
        except Exception as e:
            logger.error(f"New Places API lookup failed for {restaurant_name}: {e}")
            return None

_enricher: Optional[GooglePlacesEnricher] = None

def get_enricher() -> GooglePlacesEnricher:
    global _enricher
    if _enricher is None:
        _enricher = GooglePlacesEnricher()
    return _enricher