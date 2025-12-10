"""LLM extraction models."""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field

from .enums import SourceType, SentimentLabel


class ExtractedRestaurant(BaseModel):
    """Restaurant data extracted by LLM from text."""
    name: str = Field(..., description="Restaurant name")
    vibe: Optional[str] = Field(None, description="Atmosphere description")
    cuisine_tags: List[str] = Field(default_factory=list)
    recommended_dishes: List[str] = Field(default_factory=list)
    price_hint: Optional[str] = Field(None, description="Price mentions")
    sentiment: Optional[str] = Field(None, description="Overall sentiment")


class SentimentAnalysis(BaseModel):
    """Sentiment analysis result from LLM."""
    overall_score: float = Field(..., ge=-1.0, le=1.0, description="-1 to 1 sentiment")
    label: SentimentLabel
    aspects: Dict[str, float] = Field(
        default_factory=dict,
        description="Aspect scores: food, service, ambiance, value"
    )
    summary: Optional[str] = None


class ExtractionResult(BaseModel):
    """Full extraction result from LLM processing."""
    restaurants: List[ExtractedRestaurant]
    sentiment: Optional[SentimentAnalysis] = None
    raw_content: str
    source_url: str
    source_type: SourceType
