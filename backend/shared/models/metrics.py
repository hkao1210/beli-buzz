from datetime import datetime
from pydantic import BaseModel, Field

class RestaurantMetrics(BaseModel):
    """Simplified Proprietary Metrics."""
    restaurant_id: str
    buzz_score: float = 0.0        # 0-100 (Hype meter)
    sentiment_score: float = 0.0   # 0-10 (Quality meter)
    total_mentions: int = 0
    is_trending: bool = False
    last_updated_at: datetime = Field(default_factory=datetime.now)