"""
LLM-Powered Restaurant Extraction
=================================
Uses Groq/Llama to extract restaurant data and sentiment from text.
"""

import os
import json
import logging
from typing import List, Optional, Dict, Any

from groq import Groq
from dotenv import load_dotenv

from shared.models import (
    ExtractedRestaurant,
    SentimentAnalysis,
    SentimentLabel,
    ScrapedContent,
)

load_dotenv()

logger = logging.getLogger(__name__)


# =============================================================================
# PROMPTS
# =============================================================================

EXTRACTION_PROMPT = """You are a Toronto restaurant data extractor. Extract restaurant information from this text.

For EACH restaurant mentioned in Toronto, extract:
- name: The exact restaurant name (be precise)
- vibe: A short description of the atmosphere/vibe (e.g., "cozy date night spot", "casual family-friendly", "upscale fine dining", "trendy brunch spot")
- cuisine_tags: List of cuisine types (e.g., ["Japanese", "Ramen"], ["Italian", "Pizza"], ["Thai", "Southeast Asian"])
- recommended_dishes: Specific dishes mentioned positively (e.g., ["Khao Soi", "Pad Thai", "Mango Sticky Rice"])
- price_hint: Any price mentions (e.g., "affordable", "splurge", "$$", "under $20")
- sentiment: Overall sentiment about this restaurant ("positive", "negative", "neutral", "mixed")

IMPORTANT:
- Only extract REAL restaurants in Toronto, Canada
- Be precise with restaurant names (include "The" if part of name)
- Extract cuisine_tags that are specific (e.g., "Ramen" not just "Asian")
- Include specific dishes if mentioned, not generic ones

TEXT TO ANALYZE:
{content}

Return ONLY valid JSON array. No explanation, no markdown:
[{{"name": "...", "vibe": "...", "cuisine_tags": [...], "recommended_dishes": [...], "price_hint": "...", "sentiment": "..."}}]

If no Toronto restaurants found, return: []"""


SENTIMENT_PROMPT = """Analyze the sentiment of this restaurant review/discussion.

Provide:
1. overall_score: A score from -1.0 (very negative) to 1.0 (very positive)
2. label: One of "positive", "negative", "neutral", or "mixed"
3. aspects: Rate each aspect from -1.0 to 1.0 if mentioned:
   - food: Quality and taste of food
   - service: Staff friendliness and attentiveness  
   - ambiance: Atmosphere, decor, noise level
   - value: Price-to-quality ratio
4. summary: One sentence summary of the sentiment

TEXT:
{content}

Return ONLY valid JSON:
{{"overall_score": 0.8, "label": "positive", "aspects": {{"food": 0.9, "service": 0.7}}, "summary": "..."}}"""


# =============================================================================
# EXTRACTOR CLASS
# =============================================================================

class RestaurantExtractor:
    """
    Uses Groq LLM to extract restaurant data and analyze sentiment.
    """
    
    def __init__(self):
        self.client = self._init_groq()
        self.model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    
    def _init_groq(self) -> Optional[Groq]:
        """Initialize Groq client."""
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY not set")
            return None
        return Groq(api_key=api_key)
    
    def _call_llm(self, prompt: str, max_tokens: int = 2000) -> Optional[str]:
        """Make a call to Groq LLM."""
        if not self.client:
            return None
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None
    
    def _parse_json(self, text: str) -> Any:
        """Parse JSON from LLM response, handling markdown code blocks."""
        if not text:
            return None
        
        # Remove markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json) and last line (```)
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        
        # Handle ```json prefix
        if text.startswith("json"):
            text = text[4:].strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.debug(f"Raw text: {text[:200]}...")
            return None
    
    def extract_restaurants(
        self,
        content: ScrapedContent,
        max_content_length: int = 8000,
    ) -> List[ExtractedRestaurant]:
        """
        Extract restaurant mentions from scraped content.
        
        Args:
            content: Scraped content to analyze
            max_content_length: Max chars to send to LLM
            
        Returns:
            List of extracted restaurants
        """
        if not self.client:
            logger.warning("Groq client not available, skipping extraction")
            return []
        
        # Truncate content if too long
        text = content.raw_text[:max_content_length]
        
        prompt = EXTRACTION_PROMPT.format(content=text)
        response = self._call_llm(prompt)
        
        if not response:
            return []
        
        parsed = self._parse_json(response)
        if not parsed or not isinstance(parsed, list):
            return []
        
        restaurants = []
        for item in parsed:
            try:
                restaurant = ExtractedRestaurant(
                    name=item.get("name", ""),
                    vibe=item.get("vibe"),
                    cuisine_tags=item.get("cuisine_tags", []),
                    recommended_dishes=item.get("recommended_dishes", []),
                    price_hint=item.get("price_hint"),
                    sentiment=item.get("sentiment"),
                )
                if restaurant.name:  # Only add if name exists
                    restaurants.append(restaurant)
            except Exception as e:
                logger.warning(f"Failed to parse restaurant: {e}")
                continue
        
        logger.info(f"Extracted {len(restaurants)} restaurants from {content.source_url}")
        return restaurants
    
    def analyze_sentiment(
        self,
        content: ScrapedContent,
        max_content_length: int = 4000,
    ) -> Optional[SentimentAnalysis]:
        """
        Analyze sentiment of content.
        
        Args:
            content: Scraped content to analyze
            max_content_length: Max chars to send to LLM
            
        Returns:
            SentimentAnalysis or None
        """
        if not self.client:
            return None
        
        text = content.raw_text[:max_content_length]
        prompt = SENTIMENT_PROMPT.format(content=text)
        response = self._call_llm(prompt, max_tokens=500)
        
        if not response:
            return None
        
        parsed = self._parse_json(response)
        if not parsed or not isinstance(parsed, dict):
            return None
        
        try:
            label_str = parsed.get("label", "neutral").lower()
            label = SentimentLabel(label_str) if label_str in [e.value for e in SentimentLabel] else SentimentLabel.NEUTRAL
            
            return SentimentAnalysis(
                overall_score=float(parsed.get("overall_score", 0)),
                label=label,
                aspects=parsed.get("aspects", {}),
                summary=parsed.get("summary"),
            )
        except Exception as e:
            logger.warning(f"Failed to parse sentiment: {e}")
            return None
    
    def process_content(
        self,
        content: ScrapedContent,
    ) -> tuple[List[ExtractedRestaurant], Optional[SentimentAnalysis]]:
        """
        Full processing: extract restaurants and analyze sentiment.
        
        Args:
            content: Scraped content
            
        Returns:
            Tuple of (restaurants, sentiment)
        """
        restaurants = self.extract_restaurants(content)
        sentiment = self.analyze_sentiment(content) if restaurants else None
        
        return restaurants, sentiment


# =============================================================================
# CLI for testing
# =============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    extractor = RestaurantExtractor()
    
    # Test extraction
    test_content = ScrapedContent(
        source_type="reddit",
        source_url="https://reddit.com/test",
        raw_text="""
        Just tried Pai Northern Thai Kitchen on Duncan St for the first time - 
        the khao soi was incredible! Rich, creamy curry with perfectly crispy noodles.
        Also had the pad thai which was solid but the khao soi is the star.
        
        The place was packed even on a Tuesday. Definitely recommend going early
        to avoid the wait. Great date night spot, cozy atmosphere.
        
        Also been meaning to try Seven Lives in Kensington for their fish tacos.
        Heard they're the best in the city.
        """,
    )
    
    restaurants = extractor.extract_restaurants(test_content)
    for r in restaurants:
        print(f"\n{r.name}: {r.cuisine_tags}")
        print(f"  Vibe: {r.vibe}")
        print(f"  Dishes: {r.recommended_dishes}")

