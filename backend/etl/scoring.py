"""
Belly-Buzz Scoring Engine
=========================
Calculates Buzz Score, Viral Score, and Sentiment Score for restaurants.
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime, timedelta

from models import (
    Restaurant,
    SocialMention,
    RestaurantScores,
    SentimentLabel,
    SourceType,
)

logger = logging.getLogger(__name__)


# =============================================================================
# SCORE WEIGHTS
# =============================================================================

# Viral Score weights (social engagement)
VIRAL_WEIGHTS = {
    "reddit_score": 0.3,        # Reddit upvotes
    "reddit_comments": 0.3,     # Reddit comments
    "recency": 0.2,             # How recent the mention is
    "engagement_rate": 0.2,     # Comments/score ratio
}

# Buzz Score weights (overall score)
BUZZ_WEIGHTS = {
    "sentiment": 0.35,          # Sentiment score
    "viral": 0.25,              # Viral score  
    "mentions": 0.20,           # Number of mentions
    "pro_review": 0.10,         # Professional reviews (Eater, BlogTO)
    "google_rating": 0.10,      # Google rating
}

# Source credibility scores
SOURCE_CREDIBILITY = {
    SourceType.EATER: 1.0,
    SourceType.TORONTO_LIFE: 1.0,
    SourceType.BLOGTO: 0.9,
    SourceType.REDDIT: 0.7,
    SourceType.INSTAGRAM: 0.6,
    SourceType.MANUAL: 0.5,
}


# =============================================================================
# SCORING FUNCTIONS
# =============================================================================

def calculate_viral_score(mentions: List[SocialMention]) -> float:
    """
    Calculate viral score from social mentions.
    
    Viral Score (0-10) measures social engagement:
    - Reddit upvotes and comments
    - Recency of mentions
    - Engagement rate
    
    Args:
        mentions: List of social mentions
        
    Returns:
        Viral score from 0 to 10
    """
    if not mentions:
        return 0.0
    
    total_score = 0.0
    now = datetime.now()
    
    for mention in mentions:
        mention_score = 0.0
        
        # Reddit score component
        if mention.reddit_score:
            # Logarithmic scale: 100 upvotes = ~4.6, 1000 = ~6.9
            import math
            reddit_component = min(math.log1p(mention.reddit_score) / 2, 5)
            mention_score += reddit_component * VIRAL_WEIGHTS["reddit_score"]
        
        # Comment component
        if mention.reddit_num_comments:
            comment_component = min(math.log1p(mention.reddit_num_comments) / 1.5, 5)
            mention_score += comment_component * VIRAL_WEIGHTS["reddit_comments"]
        
        # Recency component (decay over 30 days)
        if mention.posted_at:
            days_old = (now - mention.posted_at).days if isinstance(mention.posted_at, datetime) else 30
            recency_factor = max(0, 1 - (days_old / 30))
            mention_score += recency_factor * 5 * VIRAL_WEIGHTS["recency"]
        
        # Engagement rate (comments per 100 upvotes)
        if mention.reddit_score and mention.reddit_num_comments:
            engagement = min(mention.reddit_num_comments / max(mention.reddit_score, 1) * 10, 5)
            mention_score += engagement * VIRAL_WEIGHTS["engagement_rate"]
        
        total_score += mention_score
    
    # Average across mentions, cap at 10
    avg_score = total_score / len(mentions)
    return min(round(avg_score, 2), 10.0)


def calculate_sentiment_score(mentions: List[SocialMention]) -> float:
    """
    Calculate average sentiment score from mentions.
    
    Sentiment Score (0-10) based on LLM analysis:
    - Maps -1 to 1 range to 0 to 10
    - Weights by source credibility
    
    Args:
        mentions: List of social mentions with sentiment analysis
        
    Returns:
        Sentiment score from 0 to 10
    """
    if not mentions:
        return 5.0  # Neutral default
    
    weighted_sum = 0.0
    weight_total = 0.0
    
    for mention in mentions:
        if mention.sentiment_score is None:
            continue
        
        # Get source credibility weight
        try:
            source_type = SourceType(mention.source_type) if isinstance(mention.source_type, str) else mention.source_type
            credibility = SOURCE_CREDIBILITY.get(source_type, 0.5)
        except:
            credibility = 0.5
        
        # Convert -1 to 1 range to 0 to 10
        normalized_score = (mention.sentiment_score + 1) * 5
        
        weighted_sum += normalized_score * credibility
        weight_total += credibility
    
    if weight_total == 0:
        return 5.0
    
    return round(weighted_sum / weight_total, 2)


def calculate_pro_score(mentions: List[SocialMention]) -> float:
    """
    Calculate professional review score.
    
    Pro Score (0-10) based on mentions from professional sources:
    - Eater, BlogTO, Toronto Life
    
    Args:
        mentions: List of social mentions
        
    Returns:
        Pro score from 0 to 10
    """
    pro_sources = {SourceType.EATER, SourceType.BLOGTO, SourceType.TORONTO_LIFE}
    
    pro_mentions = [
        m for m in mentions 
        if m.source_type in pro_sources or (isinstance(m.source_type, str) and m.source_type in [s.value for s in pro_sources])
    ]
    
    if not pro_mentions:
        return 0.0
    
    # Score based on number of pro mentions and sentiment
    base_score = min(len(pro_mentions) * 2, 5)  # Up to 5 points for quantity
    
    # Add sentiment bonus
    sentiment_bonus = 0
    for mention in pro_mentions:
        if mention.sentiment_score and mention.sentiment_score > 0.5:
            sentiment_bonus += 1
    
    sentiment_bonus = min(sentiment_bonus, 5)  # Up to 5 points for positive sentiment
    
    return min(base_score + sentiment_bonus, 10.0)


def calculate_buzz_score(
    sentiment_score: float,
    viral_score: float,
    pro_score: float,
    total_mentions: int,
    google_rating: Optional[float] = None,
) -> float:
    """
    Calculate the overall Belly Buzz Score.
    
    Buzz Score (0-20) combines all factors:
    - Sentiment analysis
    - Social viral engagement
    - Professional reviews
    - Total mentions
    - Google rating
    
    Args:
        sentiment_score: Sentiment score (0-10)
        viral_score: Viral score (0-10)
        pro_score: Professional review score (0-10)
        total_mentions: Number of mentions
        google_rating: Google Places rating (0-5)
        
    Returns:
        Buzz score from 0 to 20
    """
    import math
    
    # Mentions component (logarithmic, caps at ~10 for 100+ mentions)
    mentions_component = min(math.log1p(total_mentions) * 2.5, 10)
    
    # Google rating component (0-5 scaled to 0-10)
    google_component = (google_rating * 2) if google_rating else 5.0
    
    # Weighted combination
    buzz = (
        sentiment_score * BUZZ_WEIGHTS["sentiment"] +
        viral_score * BUZZ_WEIGHTS["viral"] +
        mentions_component * BUZZ_WEIGHTS["mentions"] +
        pro_score * BUZZ_WEIGHTS["pro_review"] +
        google_component * BUZZ_WEIGHTS["google_rating"]
    )
    
    # Scale to 0-20 range
    buzz_scaled = buzz * 2
    
    return round(min(buzz_scaled, 20.0), 1)


def calculate_all_scores(
    mentions: List[SocialMention],
    google_rating: Optional[float] = None,
) -> RestaurantScores:
    """
    Calculate all scores for a restaurant.
    
    Args:
        mentions: List of social mentions
        google_rating: Google Places rating
        
    Returns:
        RestaurantScores object with all scores
    """
    sentiment = calculate_sentiment_score(mentions)
    viral = calculate_viral_score(mentions)
    pro = calculate_pro_score(mentions)
    total = len(mentions)
    
    buzz = calculate_buzz_score(
        sentiment_score=sentiment,
        viral_score=viral,
        pro_score=pro,
        total_mentions=total,
        google_rating=google_rating,
    )
    
    return RestaurantScores(
        buzz_score=buzz,
        sentiment_score=sentiment,
        viral_score=viral,
        pro_score=pro,
        total_mentions=total,
    )


def update_restaurant_scores(
    restaurant: Restaurant,
    mentions: List[SocialMention],
) -> Restaurant:
    """
    Update a restaurant's scores based on its mentions.
    
    Args:
        restaurant: Restaurant to update
        mentions: Social mentions for this restaurant
        
    Returns:
        Updated restaurant
    """
    scores = calculate_all_scores(
        mentions=mentions,
        google_rating=restaurant.google_rating,
    )
    
    restaurant.buzz_score = scores.buzz_score
    restaurant.sentiment_score = scores.sentiment_score
    restaurant.viral_score = scores.viral_score
    restaurant.pro_score = scores.pro_score
    restaurant.total_mentions = scores.total_mentions
    
    # Check if trending (high recent activity)
    recent_mentions = [
        m for m in mentions 
        if m.posted_at and (datetime.now() - m.posted_at).days < 7
    ]
    restaurant.is_trending = len(recent_mentions) >= 2 and scores.viral_score > 5
    
    return restaurant


# =============================================================================
# CLI for testing
# =============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test with mock mentions
    from datetime import datetime
    
    mock_mentions = [
        SocialMention(
            restaurant_name="Pai Northern Thai",
            source_type=SourceType.REDDIT,
            source_url="https://reddit.com/test1",
            raw_text="Amazing khao soi!",
            reddit_score=150,
            reddit_num_comments=45,
            sentiment_score=0.85,
            sentiment_label=SentimentLabel.POSITIVE,
            posted_at=datetime.now() - timedelta(days=2),
        ),
        SocialMention(
            restaurant_name="Pai Northern Thai",
            source_type=SourceType.BLOGTO,
            source_url="https://blogto.com/test",
            raw_text="Best Thai in Toronto",
            sentiment_score=0.9,
            sentiment_label=SentimentLabel.POSITIVE,
            posted_at=datetime.now() - timedelta(days=10),
        ),
    ]
    
    scores = calculate_all_scores(mock_mentions, google_rating=4.5)
    
    print(f"\n=== Scores ===")
    print(f"Buzz Score: {scores.buzz_score}/20")
    print(f"Sentiment Score: {scores.sentiment_score}/10")
    print(f"Viral Score: {scores.viral_score}/10")
    print(f"Pro Score: {scores.pro_score}/10")
    print(f"Total Mentions: {scores.total_mentions}")

