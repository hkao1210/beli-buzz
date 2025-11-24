"""Gemini-powered analyzer that extracts restaurant intel from unstructured text.

Falls back to Hugging Face or lightweight keyword heuristics when Gemini is not
configured so local development remains frictionless.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

try:  # Optional import so linting still succeeds without python-dotenv
    from importlib import import_module

    load_dotenv = import_module("dotenv").load_dotenv  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - handled gracefully at runtime
    def load_dotenv() -> bool:  # type: ignore[misc]
        return False

from analyzer_hf import analyze_text as hf_analyze

load_dotenv()

try:  # Optional dependency for environments without Gemini enabled
    import google.generativeai as genai  # type: ignore
except ImportError:  # pragma: no cover - handled at runtime
    genai = None

_DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
_MODEL_HANDLE = None

# Lightweight knowledge base used when large models are unavailable
_FALLBACK_HINTS = [
    {"name": "Pai Northern Thai Kitchen", "keywords": ["Pai", "Thai", "khao soi"], "summary": "Northern Thai comfort staples."},
    {"name": "Seven Lives Tacos", "keywords": ["Seven Lives", "taco", "Baja"], "summary": "Baja-style fish tacos that stay sold out."},
    {"name": "Sugo", "keywords": ["Sugo", "red sauce", "pasta"], "summary": "Classic red-sauce Italian plates."},
    {"name": "The Burger's Priest", "keywords": ["Priest", "burger"], "summary": "Smash burgers with cult status."},
]

_PROMPT = """You are a culinary trends analyst focused on Toronto restaurants.\nRead the text between <post></post> tags and extract every restaurant\nmentioned. Respond with ONLY a JSON array. Each object must contain:\n- "name": restaurant name\n- "sentiment": number from 0-10 (float allowed)\n- "summary": max 12 words describing the vibe\n- "neighbourhood": optional short label (or null)\nIf no restaurants are present return []. Avoid commentary.\n<post>\n{content}\n</post>\n"""


def _configure_model():
    """Configures and memoizes the Gemini model handle if possible."""
    global _MODEL_HANDLE
    if _MODEL_HANDLE is not None:
        return _MODEL_HANDLE

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or genai is None:
        return None

    genai.configure(api_key=api_key)
    _MODEL_HANDLE = genai.GenerativeModel(_DEFAULT_MODEL)
    return _MODEL_HANDLE


def _parse_json_blob(blob: str) -> List[Dict[str, Any]]:
    start = blob.find("[")
    end = blob.rfind("]") + 1
    if start == -1 or end == 0:
        return []
    try:
        return json.loads(blob[start:end])
    except json.JSONDecodeError:
        return []


def _call_gemini(text: str) -> List[Dict[str, Any]]:
    model = _configure_model()
    if not model:
        return []

    response = model.generate_content(_PROMPT.format(content=text[:1800]))
    candidate = getattr(response, "text", None) or "".join(
        part.text for part in getattr(response, "candidates", []) if getattr(part, "text", None)
    )
    return _parse_json_blob(candidate)


def _keyword_fallback(text: str) -> List[Dict[str, Any]]:
    text_lower = text.lower()
    matches: List[Dict[str, Any]] = []
    for hint in _FALLBACK_HINTS:
        if any(keyword.lower() in text_lower for keyword in hint["keywords"]):
            matches.append(
                {
                    "name": hint["name"],
                    "sentiment": 8.5,
                    "summary": hint["summary"],
                    "neighbourhood": None,
                }
            )
    if matches:
        return matches

    # Extremely light heuristic: detect capitalised sequences followed by \"Kitchen\", \"Bar\", etc.
    pattern = re.compile(r"([A-Z][A-Za-z'&]+(?:\s+[A-Z][A-Za-z'&]+){0,3}\s+(?:Kitchen|Bar|Cafe|Bakery|Restaurant))")
    inferred = pattern.findall(text)
    return [
        {"name": name.strip(), "sentiment": 7.0, "summary": "Toronto favorite mentioned online", "neighbourhood": None}
        for name in inferred
    ]


def extract_restaurants(text: str, provider: str | None = None) -> List[Dict[str, Any]]:
    """Primary entry point used by the daily job."""
    preference = (provider or os.getenv("ANALYZER_PROVIDER") or "gemini").lower()

    if preference.startswith("gemini"):
        gemini_results = _call_gemini(text)
        if gemini_results:
            return gemini_results

    if preference.startswith("huggingface"):
        hf_results = hf_analyze(text)
        if hf_results:
            return hf_results

    # Final fallback for offline/local dev
    return _keyword_fallback(text)


if __name__ == "__main__":  # pragma: no cover
    sample = """Checked out Pai Northern Thai Kitchen again and the khao soi is still undefeated.\nAlso swung by Seven Lives for Baja tacos."""
    print(extract_restaurants(sample))
