import os
import logging
from typing import Optional
from google.maps import places_v1
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class GooglePlaceDTO(BaseModel):
    """Internal DTO to carry data from Google to our models (Basic SKU).
    Excludes photos, ratings, and reviews to reduce API cost."""
    place_id: str
    name: str
    address: str
    latitude: float
    longitude: float
    price_level: Optional[int] = None
    google_maps_url: str

class GooglePlacesEnricher:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.client = places_v1.PlacesClient(client_options={"api_key": self.api_key}) if self.api_key else None

    def find_place(self, restaurant_name: str, city: str = "Toronto") -> Optional[GooglePlaceDTO]:
        if not self.client:
            logger.error("Google Places Client not initialized.")
            return None
        
        try:
            logger.info(f"[enricher] Starting find_place for: {restaurant_name}")
            # Request only the minimal fields (Basic SKU): id, displayName, formattedAddress, location, priceLevel, googleMapsUri
            field_mask = "places.id,places.displayName,places.formattedAddress,places.location,places.priceLevel,places.googleMapsUri"
            
            # Location bias as a dict, not a class instantiation
            request = {
                "text_query": f"{restaurant_name} {city}",
                "max_result_count": 1,
                "location_bias": {
                    "circle": {
                        "center": {"latitude": 43.6532, "longitude": -79.3832},
                        "radius": 5000.0
                    }
                }
            }
            
            logger.info(f"[enricher] Making Google Places API call...")
            response = self.client.search_text(request=request, metadata=[("x-goog-fieldmask", field_mask)])
            logger.info(f"[enricher] API response received")
            
            if not response.places:
                logger.info(f"[enricher] No places found for {restaurant_name}")
                return None
            
            place = response.places[0]
            logger.info(f"[enricher] Found place: {place.display_name.text if place.display_name else restaurant_name}")

            return GooglePlaceDTO(
                place_id=place.id,
                name=place.display_name.text if place.display_name else restaurant_name,
                address=place.formatted_address,
                latitude=place.location.latitude,
                longitude=place.location.longitude,
                price_level=int(place.price_level) if place.price_level else None,
                google_maps_url=place.google_maps_uri,
            )
        except Exception as e:
            logger.error(f"[enricher] Google Enrichment failed for {restaurant_name}: {e}")
            return None

_enricher = None
def get_enricher():
    global _enricher
    if _enricher is None:
        _enricher = GooglePlacesEnricher()
    return _enricher