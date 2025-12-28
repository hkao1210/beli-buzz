from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, field_validator
from .enums import SourceType, SentimentLabel

#POST AI OUTPUT
class SocialMention(BaseModel):
    """Social mention record for database."""
    id: Optional[str] = None
    restaurant_id: Optional[str] = None
    restaurant_name: str # Used for grouping during ingestion

    source_type: SourceType
    source_url: str
    source_id: Optional[str] = None

    title: Optional[str] = None
    raw_text: str

    # Reddit-specific
    subreddit: Optional[str] = None
    reddit_score: int = 0
    reddit_num_comments: int = 0
    author: Optional[str] = None

    # AI-extracted
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[SentimentLabel] = None
    aspects: Optional[Dict[str, float]] = None
    dishes_mentioned: List[str] = Field(default_factory=list)
    price_mentioned: Optional[str] = None
    vibe_extracted: Optional[str] = None

    engagement_score: float = 0.0
    posted_at: Optional[datetime] = None
    scraped_at: Optional[datetime] = None

    model_config = {"extra": "ignore"}

    @field_validator("reddit_score", "reddit_num_comments", mode="before")
    @classmethod
    def coerce_int(cls, v):
        return int(v) if v is not None else 0

    @field_validator("engagement_score", mode="before")
    @classmethod
    def coerce_float(cls, v):
        return float(v) if v is not None else 0.0

    @field_validator("posted_at", "scraped_at", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    @field_validator("dishes_mentioned", mode="before")
    @classmethod
    def coerce_list(cls, v):
        if v is None: return []
        if isinstance(v, str):
            import json
            try: return json.loads(v)
            except: return []
        return v