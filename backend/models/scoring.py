"""Scoring models for restaurant buzz calculation."""

from pydantic import BaseModel, Field


class RestaurantScores(BaseModel):
    """Calculated scores for a restaurant."""
    buzz_score: float = Field(0.0, description="Overall buzz score (0-20)")
    sentiment_score: float = Field(0.0, description="Avg sentiment (-1 to 1, normalized to 0-10)")
    viral_score: float = Field(0.0, description="Social engagement score (0-10)")
    pro_score: float = Field(0.0, description="Professional review score (0-10)")
    total_mentions: int = 0
