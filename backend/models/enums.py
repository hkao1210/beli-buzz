"""Enumeration types for Belly-Buzz."""

from enum import Enum


class SourceType(str, Enum):
    REDDIT = "reddit"
    EATER = "eater"
    BLOGTO = "blogto"
    TORONTO_LIFE = "toronto_life"
    INSTAGRAM = "instagram"
    MANUAL = "manual"


class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"
