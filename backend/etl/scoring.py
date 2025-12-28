"""
Belly-Buzz Simple Scoring
=========================
Consolidated scoring: Buzz (Hype/Volume) and Sentiment (Quality).
"""
import math
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from shared.models import RestaurantMetrics
from shared.models import SocialMention

logger = logging.getLogger(__name__)

def calculate_metrics(
    mentions: List[SocialMention], 
    google_rating: Optional[float] = 0.0,
    google_reviews: int = 0
) -> Tuple[float, float]:
    """
    Consolidated scoring logic.
    Returns (buzz_score, sentiment_score).
    """
    if not mentions:
        return 0.0, google_rating or 0.0

    now = datetime.now()
    total_engagement = 0.0
    sentiment_sum = 0.0
    sentiment_count = 0
    
    # 1. Process Mentions in a single pass
    for m in mentions:
        # Engagement Score (Reddit Upvotes + Comments)
        # Using log to prevent one viral post from breaking the scale
        score = float(m.reddit_score or 0)
        comments = float(m.reddit_num_comments or 0)
        engagement = math.log1p(score) + math.log1p(comments * 2)
        
        # Recency Decay (Mentions older than 30 days lose value)
        if m.posted_at:
            days_old = (now - m.posted_at.replace(tzinfo=None)).days
            decay = max(0.1, 1 - (days_old / 30))
            engagement *= decay
            
        total_engagement += engagement

        # Sentiment Average
        if m.sentiment_score is not None:
            sentiment_sum += m.sentiment_score
            sentiment_count += 1

    # 2. Calculate Final Buzz (0-100 Scale for UI)
    # Buzz = (Log of total volume) + (Decayed social engagement) + (Google Review Weight)
    volume_bonus = math.log1p(len(mentions)) * 10
    google_bonus = (google_rating or 0) * 2 # Google adds a baseline quality
    
    buzz_score = volume_bonus + total_engagement + google_bonus
    buzz_score = min(round(buzz_score, 1), 100.0)

    # 3. Calculate Final Sentiment (0-10 Scale)
    # Average LLM sentiment (usually -1 to 1) mapped to 0-10
    raw_sentiment = (sentiment_sum / sentiment_count) if sentiment_count > 0 else 0.5
    sentiment_score = round((raw_sentiment + 1) * 5, 1)

    return buzz_score, sentiment_score

def update_metrics_object(
    metrics: RestaurantMetrics, 
    mentions: List[SocialMention],
    google_rating: Optional[float] = 0.0
) -> RestaurantMetrics:
    """Updates the metrics model with simplified logic."""
    buzz, sentiment = calculate_metrics(mentions, google_rating)
    
    metrics.buzz_score = buzz
    metrics.sentiment_score = sentiment
    metrics.total_mentions = len(mentions)
    
    # Simple "Trending" flag: 2+ mentions in the last 7 days
    recent = [m for m in mentions if m.posted_at and (datetime.now() - m.posted_at.replace(tzinfo=None)).days < 7]
    metrics.is_trending = len(recent) >= 2
    
    return metrics