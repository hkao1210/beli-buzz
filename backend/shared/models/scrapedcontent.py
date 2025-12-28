from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from .enums import SourceType

class ScrapedContent(BaseModel):
    source_type: SourceType
    source_url: str
    source_id: Optional[str] = None
    title: Optional[str] = None
    raw_text: str
    author: Optional[str] = None
    posted_at: Optional[datetime] = None

    # Social-specific metadata (baselines from results.json)
    subreddit: Optional[str] = None
    reddit_score: int = 0
    reddit_num_comments: int = 0