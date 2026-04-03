import re
from datetime import date

from flatseeker.config import MAX_RENT_CHF, MAX_TOTAL_PEOPLE, MAX_TRANSIT_MINUTES, EARLIEST_MOVE_IN, LATEST_MOVE_IN, MAX_POST_AGE_DAYS
from flatseeker.scraper import ListingCard, ListingDetail
from flatseeker.parser import (
    parse_price, parse_roommate_count, parse_move_in_date, parse_location,
    parse_post_date, is_request_not_offer, is_not_housing, is_sublet, is_foreign_location,
    has_incompatible_requirements,
)
from flatseeker.maps import get_transit_time_cached
from flatseeker.cache import is_seen, mark_seen


# Categories to always skip
SKIP_CATEGORIES = {
    "workspace", "arbeitsplatz", "other rooms", "andere",
    "5+ room apartment", "5+",
}


def pass1_card_filter(cards: list[ListingCard], cache: dict) -> list[ListingCard]:
    """First pass: filter by card info only. No clicks, no API calls."""
    candidates = []

    for card in cards:
        if is_seen(cache, card.listing_id):
            continue

        # Skip unwanted categories
        cat_lower = card.category.lower().strip()
        if any(skip in cat_lower for skip in SKIP_CATEGORIES):
            mark_seen(cache, card.listing_id, "rejected_category", {
                "title": card.title, "category": card.category, "url": card.url,
            })
            continue

        card_text = f"{card.title} {card.description}"

        # Skip non-housing (cleaning, furniture, offices, etc.)
        if is_not_housing(card_text):
            mark_seen(cache, card.listing_id, "rejected_not_housing", {
                "title": card.title, "url": card.url,
            })
            continue

        # Skip requests (people looking for housing, not offering)
        if is_request_not_offer(card_text):
            mark_seen(cache, card.listing_id, "rejected_request", {
                "title": card.title, "url": card.url,
                "note": "This is a search/request, not an offer",
            })
            continue

        # Skip sublets / Zwischenmiete
        if is_sublet(card_text):
            mark_seen(cache, card.listing_id, "rejected_sublet", {
                "title": card.title, "url": card.url,
            })
            continue

        # Skip foreign locations detectable from card text
        if is_foreign_location(card_text):
            mark_seen(cache, card.listing_id, "rejected_foreign", {
                "title": card.title, "url": card.url,
            })
            continue

        # Quick price check from card text
        card_price = parse_price(card_text)
        if card_price and card_price > MAX_RENT_CHF:
            mark_seen(cache, card.listing_id, "rejected_price_card", {
                "title": card.title, "price": card_price, "url": card.url,
            })
            continue

        candidates.append(card)

    return candidates


def pass2_detail_filter(details: list[ListingDetail], cache: dict) -> list[ListingDetail]:
    """Second pass: filter by detail page info. No API calls yet."""
    candidates = []
    seen_titles = set()  # deduplication by normalized title

    for detail in details:
        card = detail.card
        full_text = detail.full_text

        # Check if detail page reveals it's a request
        if is_request_not_offer(full_text):
            mark_seen(cache, card.listing_id, "rejected_request", {
                "title": card.title, "url": card.url,
            })
            continue

        # Check non-housing from detail text
        if is_not_housing(full_text):
            mark_seen(cache, card.listing_id, "rejected_not_housing", {
                "title": card.title, "url": card.url,
            })
            continue

        # Check sublet from detail text
        if is_sublet(full_text):
            mark_seen(cache, card.listing_id, "rejected_sublet", {
                "title": card.title, "url": card.url,
            })
            continue

        # Check foreign location from detail text
        if is_foreign_location(full_text):
            mark_seen(cache, card.listing_id, "rejected_foreign", {
                "title": card.title, "url": card.url,
            })
            continue

        # Check incompatible household requirements (pronouns, vegan, etc.)
        if has_incompatible_requirements(full_text):
            mark_seen(cache, card.listing_id, "rejected_requirements", {
                "title": card.title, "url": card.url,
            })
            continue

        # Parse all fields from full text
        detail.price_chf = parse_price(full_text)
        detail.num_people = parse_roommate_count(full_text)
        detail.address = parse_location(full_text)
        post_dt = parse_post_date(full_text)
        detail.post_date = str(post_dt) if post_dt else None

        move_in = parse_move_in_date(full_text)
        if move_in:
            detail.move_in_date = str(move_in)

        # Also try parsing from structured attributes
        for key, val in detail.raw_attributes.items():
            key_lower = key.lower()
            if not detail.price_chf and any(w in key_lower for w in ["price", "preis", "miete", "rent"]):
                detail.price_chf = parse_price(val)
            if not detail.address and any(w in key_lower for w in ["address", "adresse", "location", "ort"]):
                detail.address = val
            if not detail.num_people and any(w in key_lower for w in ["person", "roommate", "mitbewohner", "wg"]):
                detail.num_people = parse_roommate_count(val)

        # Filter: price
        if detail.price_chf and detail.price_chf > MAX_RENT_CHF:
            mark_seen(cache, card.listing_id, "rejected_price", {
                "title": card.title, "price": detail.price_chf, "url": card.url,
            })
            continue

        # Filter: roommates (max 4 people total)
        if detail.num_people and detail.num_people > MAX_TOTAL_PEOPLE:
            mark_seen(cache, card.listing_id, "rejected_roommates", {
                "title": card.title, "num_people": detail.num_people, "url": card.url,
            })
            continue

        # Filter: move-in date
        if move_in and move_in > LATEST_MOVE_IN:
            mark_seen(cache, card.listing_id, "rejected_move_in", {
                "title": card.title, "move_in": str(move_in), "url": card.url,
            })
            continue

        # Filter: stale posts
        if post_dt and (date.today() - post_dt).days > MAX_POST_AGE_DAYS:
            mark_seen(cache, card.listing_id, "rejected_stale", {
                "title": card.title, "post_date": str(post_dt), "url": card.url,
                "note": f"Posted {(date.today() - post_dt).days} days ago",
            })
            continue

        # Deduplication: skip if we already have a listing with the same title
        norm_title = re.sub(r'\s+', ' ', card.title.lower().strip())
        if norm_title in seen_titles:
            mark_seen(cache, card.listing_id, "rejected_duplicate", {
                "title": card.title, "url": card.url,
            })
            continue
        seen_titles.add(norm_title)

        candidates.append(detail)

    return candidates


def pass3_transit_filter(details: list[ListingDetail], cache: dict) -> list[ListingDetail]:
    """Third pass: check transit time via Google Maps API."""
    matched = []

    for detail in details:
        card = detail.card

        if not detail.address:
            mark_seen(cache, card.listing_id, "matched_no_address", {
                "title": card.title, "price": detail.price_chf,
                "post_date": detail.post_date,
                "url": card.url, "transit_min": None,
                "note": "No address found - check manually",
            })
            matched.append(detail)
            continue

        transit_min = get_transit_time_cached(detail.address, cache)
        detail.transit_min = transit_min

        if transit_min is None:
            mark_seen(cache, card.listing_id, "matched_transit_unknown", {
                "title": card.title, "price": detail.price_chf,
                "address": detail.address, "post_date": detail.post_date,
                "url": card.url, "transit_min": None,
                "note": "Could not calculate transit time - check manually",
            })
            matched.append(detail)
            continue

        if transit_min <= MAX_TRANSIT_MINUTES:
            mark_seen(cache, card.listing_id, "matched", {
                "title": card.title, "price": detail.price_chf,
                "address": detail.address, "post_date": detail.post_date,
                "url": card.url, "transit_min": transit_min,
            })
            matched.append(detail)
        else:
            mark_seen(cache, card.listing_id, "rejected_transit", {
                "title": card.title, "price": detail.price_chf,
                "address": detail.address, "post_date": detail.post_date,
                "url": card.url, "transit_min": transit_min,
            })

    return matched
