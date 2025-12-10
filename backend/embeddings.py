"""
Embedding Service
=================
Creates vector embeddings for semantic search.
"""

import logging
from typing import List, Optional

from sentence_transformers import SentenceTransformer

from models import ExtractedRestaurant, Restaurant

logger = logging.getLogger(__name__)

# Default model - 384 dimensions, fast and good quality
DEFAULT_MODEL = "all-MiniLM-L6-v2"


class EmbeddingService:
    """
    Creates embeddings for restaurants using Sentence Transformers.
    Runs locally - no API key needed!
    """
    
    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        
    def load(self) -> bool:
        """Load the embedding model."""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            return False
    
    def embed_text(self, text: str) -> List[float]:
        """
        Create embedding vector from text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats (embedding vector)
        """
        if not self.model:
            self.load()
        
        embedding = self.model.encode(text)
        return embedding.tolist()
    
    def embed_restaurant(self, restaurant: Restaurant) -> List[float]:
        """
        Create searchable embedding from restaurant attributes.
        Combines vibe, cuisine tags, and dishes for semantic search.
        
        Args:
            restaurant: Restaurant object
            
        Returns:
            Embedding vector
        """
        # Combine all searchable text
        text_parts = []
        
        if restaurant.vibe:
            text_parts.append(restaurant.vibe)
        
        if restaurant.cuisine_tags:
            text_parts.extend(restaurant.cuisine_tags)
        
        if restaurant.recommended_dishes:
            text_parts.extend(restaurant.recommended_dishes)
        
        if restaurant.name:
            text_parts.append(restaurant.name)
        
        if restaurant.neighborhood:
            text_parts.append(restaurant.neighborhood)
        
        combined_text = " ".join(text_parts)
        
        if not combined_text.strip():
            combined_text = restaurant.name or "restaurant"
        
        return self.embed_text(combined_text)
    
    def embed_extracted(
        self,
        extracted: ExtractedRestaurant,
    ) -> List[float]:
        """
        Create embedding from extracted restaurant data.
        
        Args:
            extracted: Extracted restaurant data
            
        Returns:
            Embedding vector
        """
        text_parts = [extracted.name]
        
        if extracted.vibe:
            text_parts.append(extracted.vibe)
        
        text_parts.extend(extracted.cuisine_tags)
        text_parts.extend(extracted.recommended_dishes)
        
        combined_text = " ".join(text_parts)
        return self.embed_text(combined_text)
    
    def embed_query(self, query: str) -> List[float]:
        """
        Create embedding for a search query.
        
        Args:
            query: User search query
            
        Returns:
            Embedding vector for similarity search
        """
        return self.embed_text(query)
    
    def get_dimension(self) -> int:
        """Get the embedding dimension size."""
        if not self.model:
            self.load()
        return self.model.get_sentence_embedding_dimension()


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the singleton embedding service."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
        _embedding_service.load()
    return _embedding_service


# =============================================================================
# CLI for testing
# =============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    service = EmbeddingService()
    service.load()
    
    # Test embeddings
    queries = [
        "romantic Italian restaurant for date night",
        "cheap ramen noodles",
        "best fish tacos Toronto",
        "upscale sushi omakase",
    ]
    
    for query in queries:
        embedding = service.embed_query(query)
        print(f"\n'{query}'")
        print(f"  Dimension: {len(embedding)}")
        print(f"  First 5 values: {embedding[:5]}")

