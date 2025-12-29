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

from shared.models import ExtractedRestaurant, Restaurant

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingService:
    """
    Creates embeddings using OpenAI's embedding API.
    Used for semantic search in the Belly-Buzz discovery engine.
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

    def load(self):
        try:
            self._get_client()
            logger.info(f"Embedding service loaded with model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to load embedding service: {e}")
            raise

    def embed_text(self, text: str) -> List[float]:
        if not text or not text.strip():
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
        Create searchable embedding from core restaurant attributes.
        Uses fields available in the normalized Restaurant model.
        """
        text_parts = []

        if restaurant.name:
            text_parts.append(restaurant.name)

        if restaurant.vibe:
            text_parts.append(restaurant.vibe)

        combined_text = ". ".join(text_parts)
        if not combined_text.strip():
            combined_text = restaurant.name or "restaurant"

        return self.embed_text(combined_text)

    def embed_extracted(self, extracted: ExtractedRestaurant) -> List[float]:

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
        """Create embedding for a natural language search query."""
        return self.embed_text(query)

    def get_dimension(self) -> int:
        """Get the embedding dimension size (1536 for text-embedding-3-small)."""
        return EMBEDDING_DIMENSIONS


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service