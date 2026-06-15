"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_normalize_text(item) for item in value if item is not None)
    return str(value)


def _tokenize(text: str) -> list[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "the",
        "for",
        "in",
        "of",
        "on",
        "out",
        "with",
        "to",
        "under",
        "over",
        "size",
    }
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in stopwords]


def _contains_term(text: str, term: str) -> bool:
    if not text or not term:
        return False
    normalized_text = text.lower()
    normalized_term = term.lower().strip()
    if not normalized_term:
        return False
    if " " in normalized_term:
        return normalized_term in normalized_text
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def _size_matches(listing_size: Any, requested_size: str | None) -> bool:
    if requested_size is None:
        return True

    requested_norm = _normalize_text(requested_size).lower().strip()
    listing_norm = _normalize_text(listing_size).lower().strip()

    if not requested_norm:
        return True
    if not listing_norm:
        return False

    if requested_norm == listing_norm:
        return True
    if requested_norm in listing_norm or listing_norm in requested_norm:
        return True

    requested_tokens = set(_tokenize(requested_norm))
    listing_tokens = set(_tokenize(listing_norm))
    return bool(requested_tokens and requested_tokens.issubset(listing_tokens))


def _call_groq(prompt: str, *, temperature: float) -> str:
    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are FitFindr, a concise styling assistant for secondhand fashion.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        content = response.choices[0].message.content
        return _normalize_text(content).strip()
    except Exception:
        return ""


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()
    query_phrase = _normalize_text(description).strip().lower()
    query_tokens = _tokenize(query_phrase)

    if not query_phrase:
        return []

    scored_listings: list[tuple[float, dict]] = []

    for listing in listings:
        listing_price = listing.get("price")
        if max_price is not None and listing_price is not None and listing_price > max_price:
            continue

        if not _size_matches(listing.get("size"), size):
            continue

        title = _normalize_text(listing.get("title"))
        description_text = _normalize_text(listing.get("description"))
        category = _normalize_text(listing.get("category"))
        style_tags = _normalize_text(listing.get("style_tags"))
        colors = _normalize_text(listing.get("colors"))
        brand = _normalize_text(listing.get("brand"))

        score = 0.0

        if query_phrase in title.lower():
            score += 6.0
        if query_phrase in description_text.lower():
            score += 4.0

        for token in query_tokens:
            if _contains_term(title, token):
                score += 3.0
            if _contains_term(style_tags, token):
                score += 2.0
            if _contains_term(category, token):
                score += 2.0
            if _contains_term(description_text, token):
                score += 1.5
            if _contains_term(colors, token):
                score += 1.0
            if _contains_term(brand, token):
                score += 1.0

        if score > 0:
            scored_listings.append((score, listing))

    scored_listings.sort(
        key=lambda item: (
            -item[0],
            item[1].get("price", float("inf")),
            _normalize_text(item[1].get("title")).lower(),
        )
    )
    return [listing for _, listing in scored_listings]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    wardrobe_items = (wardrobe or {}).get("items") or []

    item_summary = (
        f"Item name: {_normalize_text(new_item.get('title'))}\n"
        f"Category: {_normalize_text(new_item.get('category'))}\n"
        f"Style tags: {_normalize_text(new_item.get('style_tags'))}\n"
        f"Colors: {_normalize_text(new_item.get('colors'))}\n"
        f"Condition: {_normalize_text(new_item.get('condition'))}\n"
        f"Price: ${_normalize_text(new_item.get('price'))}\n"
        f"Platform: {_normalize_text(new_item.get('platform'))}"
    )

    if not wardrobe_items:
        prompt = (
            "Give 1-2 sentences of general styling advice for the thrifted item below. "
            "The user has no wardrobe items saved, so do not reference specific closet pieces. "
            "Focus on silhouette, layering, shoes, and the overall vibe.\n\n"
            f"{item_summary}"
        )
        result = _call_groq(prompt, temperature=0.7)
        if result:
            return result
        return (
            f"Try styling {_normalize_text(new_item.get('title')) or 'this piece'} with relaxed denim or cargo bottoms, "
            "chunky sneakers or boots, and one light layer to keep the silhouette balanced. "
            "Use one tuck or rolled sleeves to add shape while keeping the overall vibe casual."
        )

    wardrobe_lines = []
    for item in wardrobe_items:
        wardrobe_lines.append(
            "- "
            + ", ".join(
                [
                    f"name: {_normalize_text(item.get('name'))}",
                    f"category: {_normalize_text(item.get('category'))}",
                    f"colors: {_normalize_text(item.get('colors'))}",
                    f"style_tags: {_normalize_text(item.get('style_tags'))}",
                    f"notes: {_normalize_text(item.get('notes'))}",
                ]
            )
        )

    prompt = (
        "Suggest 1-2 outfit ideas that combine the thrifted item with specific wardrobe pieces. "
        "Use real item names from the wardrobe and explain why the combo works. "
        "Include at least one practical styling note such as tucking, layering, cuffing, or footwear.\n\n"
        f"Thrifted item:\n{item_summary}\n\n"
        f"Wardrobe items:\n" + "\n".join(wardrobe_lines)
    )
    result = _call_groq(prompt, temperature=0.7)
    if result:
        return result
    first_item_name = _normalize_text(wardrobe_items[0].get("name")) if wardrobe_items else "a staple bottom"
    return (
        f"Start with {_normalize_text(new_item.get('title')) or 'the new item'} and pair it with {first_item_name} for a clean base. "
        "Add a simple layer and finish with chunky sneakers or boots; a small front tuck or cuff keeps the look intentional."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Error: outfit suggestion is missing, so I can't create a fit card."

    prompt = (
        "Write a casual 2-4 sentence fit card caption based on the outfit idea below. "
        "The caption should sound like a real social post, not a product description. "
        "Mention the item name, price, and platform naturally exactly once each. "
        "Keep it specific, stylish, and a little playful.\n\n"
        f"Item name: {_normalize_text(new_item.get('title'))}\n"
        f"Price: ${_normalize_text(new_item.get('price'))}\n"
        f"Platform: {_normalize_text(new_item.get('platform'))}\n"
        f"Outfit idea: {outfit.strip()}"
    )

    result = _call_groq(prompt, temperature=1.05)
    if not result:
        title = _normalize_text(new_item.get("title")) or "this piece"
        price = _normalize_text(new_item.get("price")) or "unknown"
        platform = _normalize_text(new_item.get("platform")) or "a resale app"
        return (
            f"thrifted {title} for ${price} on {platform} and built a look around it today. "
            f"{outfit.strip()}"
        )
    return result
