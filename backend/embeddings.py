"""
Embedding Service
=================
Creates vector embeddings for semantic search using OpenAI.
"""

import os
import logging
from typing import List, Optional

from openai import OpenAI
from dotenv import load_dotenv

from models import ExtractedRestaurant, Restaurant

load_dotenv()

logger = logging.getLogger(__name__)

# OpenAI embedding model - 1536 dimensions, great quality
DEFAULT_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingService:
    """
    Creates embeddings using OpenAI's embedding API.
    Fast, high quality, no local model needed.
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        """Get or create OpenAI client."""
        if self.client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            self.client = OpenAI(api_key=api_key)
        return self.client

    def embed_text(self, text: str) -> List[float]:
        """
        Create embedding vector from text.

        Args:
            text: Text to embed

        Returns:
            List of floats (embedding vector)
        """
        if not text.strip():
            text = "restaurant"

        try:
            response = self._get_client().embeddings.create(
                input=text,
                model=self.model,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            raise

    def embed_restaurant(self, restaurant: Restaurant) -> List[float]:
        """
        Create searchable embedding from restaurant attributes.
        Combines vibe, cuisine tags, and dishes for semantic search.

        Args:
            restaurant: Restaurant object

        Returns:
            Embedding vector
        """
        text_parts = []

        if restaurant.name:
            text_parts.append(restaurant.name)

        if restaurant.vibe:
            text_parts.append(restaurant.vibe)

        if restaurant.cuisine_tags:
            text_parts.append(", ".join(restaurant.cuisine_tags))

        if restaurant.recommended_dishes:
            text_parts.append("dishes: " + ", ".join(restaurant.recommended_dishes))

        combined_text = ". ".join(text_parts)

        if not combined_text.strip():
            combined_text = restaurant.name or "restaurant"

        return self.embed_text(combined_text)

    def embed_extracted(self, extracted: ExtractedRestaurant) -> List[float]:
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

        if extracted.cuisine_tags:
            text_parts.append(", ".join(extracted.cuisine_tags))

        if extracted.recommended_dishes:
            text_parts.append("dishes: " + ", ".join(extracted.recommended_dishes))

        combined_text = ". ".join(text_parts)
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
        return EMBEDDING_DIMENSIONS


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the singleton embedding service."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


# =============================================================================
# CLI for testing
# =============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    service = get_embedding_service()

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
