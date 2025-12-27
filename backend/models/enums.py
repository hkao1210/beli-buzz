"""Enumeration types for Belly-Buzz."""

from enum import Enum


class SourceType(str, Enum):
    BLOG = "blog"
    SOCIAL = "social"


class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"
