from dataclasses import dataclass
from typing import Optional
from contextlib import asynccontextmanager

from embeddings import EmbeddingService
from .scrapers.content import ContentScraper
from .llm.extractor import RestaurantExtractor
from .enrichment import GooglePlacesEnricher


@dataclass
class Services:
    """Container for all pipeline services."""
    embedder: EmbeddingService
    extractor: RestaurantExtractor
    enricher: GooglePlacesEnricher
    content_scraper: Optional[ContentScraper] = None


@asynccontextmanager
async def create_services(
):
    """
    Initialize all services with proper lifecycle management.
    
    Usage:
        async with create_services() as services:
            # use services.embedder, services.extractor, etc.
    """
    # Initialize services (do blocking init before async work)
    embedder = EmbeddingService()
    extractor = RestaurantExtractor()
    enricher = GooglePlacesEnricher()
    
    content_scraper = ContentScraper()
    
    services = Services(
        embedder=embedder,
        extractor=extractor,
        enricher=enricher,
        content_scraper=content_scraper,
    )
    
    try:
        yield services
    finally:
        # Cleanup if needed (close connections, etc.)
        pass