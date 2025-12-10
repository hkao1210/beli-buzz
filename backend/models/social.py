"""Social mention models for scraped content."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .enums import SourceType


class RedditPost(BaseModel):
    """Raw Reddit post data from PRAW."""
    id: str
    title: str
    selftext: str
    subreddit: str
    score: int
    num_comments: int
    author: str
    url: str
    created_utc: float
    permalink: str


class ScrapedContent(BaseModel):
    """Content scraped from any source."""
    source_type: SourceType
    source_url: str
    source_id: Optional[str] = None
    title: Optional[str] = None
    raw_text: str
    author: Optional[str] = None
    posted_at: Optional[datetime] = None

    # Reddit-specific
    subreddit: Optional[str] = None
    reddit_score: Optional[int] = None
    reddit_num_comments: Optional[int] = None
