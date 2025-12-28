"""
Google Places Enrichment
========================
Enriches restaurant data with Google Places API.
"""

import os
import re
import logging
from typing import Optional, List

import googlemaps
from dotenv import load_dotenv

from shared.models import GooglePlaceData, ExtractedRestaurant

load_dotenv()

logger = logging.getLogger(__name__)


class GooglePlacesEnricher:
    """
    Enriches restaurant data using Google Places API.
    
    Requires GOOGLE_MAPS_API_KEY environment variable.
    """
    
    def __init__(self):
        self.client = self._init_client()
        
    def _init_client(self) -> Optional[googlemaps.Client]:
        """Initialize Google Maps client."""
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_MAPS_API_KEY not set")
            return None
        
        try:
            client = googlemaps.Client(key=api_key)
            logger.info("Google Maps client initialized")
            return client
        except Exception as e:
            logger.error(f"Failed to initialize Google Maps: {e}")
            return None

    def find_place(
        self,
        restaurant_name: str,
        city: str = "Toronto",
    ) -> Optional[GooglePlaceData]:
        """
        Find a restaurant on Google Places.
        
        Args:
            restaurant_name: Name of the restaurant
            city: City to search in (default: Toronto)
            
        Returns:
            GooglePlaceData or None if not found
        """
        if not self.client:
            logger.warning("Google Maps client not available")
            return None
        
        try:
            query = f"{restaurant_name} restaurant {city}"
            
            result = self.client.find_place(
                input=query,
                input_type="textquery",
                fields=[
                    "place_id",
                    "name",
                    "formatted_address",
                    "geometry",
                    "price_level",
                    "rating",
                    "user_ratings_total",
                    "photos",
                    "types",
                ]
            )
            
            if not result.get("candidates"):
                logger.warning(f"No Google Places result for: {restaurant_name}")
                return None
            
            place = result["candidates"][0]
            place_id = place["place_id"]
            
            # Get photo URL if available
            photo_ref = None
            photo_url = None
            if place.get("photos"):
                photo_ref = place["photos"][0].get("photo_reference")
                if photo_ref:
                    photo_url = self._get_photo_url(photo_ref)
            
            address = place.get("formatted_address", "")

            return GooglePlaceData(
                place_id=place_id,
                name=place.get("name", restaurant_name),
                address=address,
                city=city,
                latitude=place["geometry"]["location"]["lat"],
                longitude=place["geometry"]["location"]["lng"],
                price_level=place.get("price_level"),
                rating=place.get("rating"),
                reviews_count=place.get("user_ratings_total"),
                google_maps_url=f"https://www.google.com/maps/place/?q=place_id:{place_id}",
                photo_reference=photo_ref,
                photo_url=photo_url,
                types=place.get("types", []),
            )
            
        except Exception as e:
            logger.error(f"Google Places lookup failed for {restaurant_name}: {e}")
            return None
    
    def _get_photo_url(
        self,
        photo_reference: str,
        max_width: int = 400,
    ) -> Optional[str]:
        """Generate Google Places photo URL."""
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not photo_reference or not api_key:
            return None
        
        return (
            f"https://maps.googleapis.com/maps/api/place/photo"
            f"?maxwidth={max_width}"
            f"&photo_reference={photo_reference}"
            f"&key={api_key}"
        )
    
    def enrich_extracted(
        self,
        extracted: ExtractedRestaurant,
        city: str = "Toronto",
    ) -> Optional[GooglePlaceData]:
        """
        Enrich an extracted restaurant with Google Places data.
        
        Args:
            extracted: Extracted restaurant data from LLM
            city: City to search in
            
        Returns:
            GooglePlaceData or None
        """
        return self.find_place(extracted.name, city)
    
    def batch_enrich(
        self,
        restaurants: List[ExtractedRestaurant],
        city: str = "Toronto",
    ) -> dict[str, Optional[GooglePlaceData]]:
        """
        Enrich multiple restaurants.
        
        Args:
            restaurants: List of extracted restaurants
            city: City to search in
            
        Returns:
            Dict mapping restaurant name to GooglePlaceData
        """
        results = {}
        
        for restaurant in restaurants:
            place_data = self.enrich_extracted(restaurant, city)
            results[restaurant.name] = place_data
            
            if place_data:
                logger.info(f"Enriched: {restaurant.name} -> {place_data.address}")
            else:
                logger.warning(f"Failed to enrich: {restaurant.name}")
        
        return results


# Singleton instance
_enricher: Optional[GooglePlacesEnricher] = None


def get_enricher() -> GooglePlacesEnricher:
    """Get or create the singleton enricher."""
    global _enricher
    if _enricher is None:
        _enricher = GooglePlacesEnricher()
    return _enricher


# =============================================================================
# CLI for testing
# =============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    enricher = GooglePlacesEnricher()
    
    if enricher.client:
        # Test with known Toronto restaurants
        test_restaurants = [
            "Pai Northern Thai Kitchen",
            "Seven Lives Tacos",
            "Ramen Isshin",
        ]
        
        for name in test_restaurants:
            place = enricher.find_place(name)
            if place:
                print(f"\n{place.name}")
                print(f"  Address: {place.address}")
                print(f"  Rating: {place.rating} ({place.reviews_count} reviews)")
                print(f"  Price Level: {place.price_level}")
                print(f"  Coords: ({place.latitude}, {place.longitude})")

