"""LLM extraction models."""
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from .enums import SentimentLabel

class ExtractedRestaurant(BaseModel):
    """Data identified by AI within a text block."""
    name: str
    vibe: Optional[str] = None
    cuisine_tags: List[str] = Field(default_factory=list)
    recommended_dishes: List[str] = Field(default_factory=list)
    price_hint: Optional[str] = None
    sentiment: Optional[str] = None

class SentimentAnalysis(BaseModel):
    """Overall sentiment for a text block or specific mention."""
    overall_score: float = Field(..., ge=-1.0, le=1.0)
    label: SentimentLabel
    aspects: Dict[str, float] = Field(default_factory=dict)
    summary: Optional[str] = None