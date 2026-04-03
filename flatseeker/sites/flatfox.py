import json
import time
import requests
from playwright.sync_api import Page

from flatseeker.sites.base import BaseSite
from flatseeker.scraper import ListingCard, ListingDetail
from flatseeker.config import MAX_RENT_CHF, DATA_DIR, FLATFOX_SCAN_WINDOW


class FlatfoxSite(BaseSite):
    """Flatfox.ch scraper using their public JSON API (no Playwright needed).

    The API has no server-side filtering -- it returns all ~33k Swiss listings.
    Strategy: on first run, scan everything and save a high-water mark (max PK).
    On subsequent runs, only scan listings newer than the high-water mark.
    """

    name = "flatfox"
    display_name = "flatfox.ch"
    base_url = "https://flatfox.ch"

    API_URL = "https://flatfox.ch/api/v1/public-listing/"
    PAGE_SIZE = 100

    # Basel postal codes
    BASEL_ZIPCODES = set(range(4000, 4100))

    # Object types we care about (WG rooms primarily, small studios secondarily)
    TARGET_CATEGORIES = {"SHARED"}
    TARGET_TYPES = {
        "SHARED_FLAT", "SINGLE_ROOM",  # WG rooms
        "STUDIO", "FURNISHED_FLAT",     # small places that might be affordable
    }

    # Local state file for tracking scan progress
    STATE_FILE = DATA_DIR / "flatfox_state.json"

    def __init__(self):
        self._listing_data: dict[str, dict] = {}
        self._state = self._load_state()

    def scrape_cards(self, page: Page, known_ids: set[str] | None = None) -> list[ListingCard]:
        """Fetch listings from Flatfox API, filter for Basel rooms."""
        print(f"Navigating to {self.display_name} API...")

        # Step 1: Get total count
        resp = self._api_get({"limit": 1, "offset": 0})
        if resp is None:
            print("  [ERROR] Could not reach Flatfox API")
            return []
        total_count = resp.get("count", 0)
        print(f"  Total listings on Flatfox: {total_count:,}")

        # Step 2: Determine scan range
        max_pk_seen = self._state.get("max_pk", 0)
        scan_window = FLATFOX_SCAN_WINDOW
        start_offset = max(0, total_count - scan_window)
        if max_pk_seen > 0:
            print(f"  Incremental scan: last {scan_window:,} listings (max_pk={max_pk_seen})")
        else:
            print(f"  First run: scanning last {scan_window:,} listings")

        # Step 3: Paginate and filter
        cards = []
        offset = start_offset
        pages_fetched = 0
        max_pk_this_run = max_pk_seen

        while offset < total_count:
            resp = self._api_get({"limit": self.PAGE_SIZE, "offset": offset})
            if resp is None:
                print(f"  [WARN] API request failed at offset={offset}, stopping")
                break

            results = resp.get("results", [])
            if not results:
                break

            for listing in results:
                pk = listing.get("pk", 0)
                max_pk_this_run = max(max_pk_this_run, pk)

                # On incremental runs, skip listings we've already seen
                if max_pk_seen > 0 and pk <= max_pk_seen:
                    continue

                if self._matches_criteria(listing):
                    card = self._to_listing_card(listing)
                    cards.append(card)
                    self._listing_data[str(pk)] = listing

            offset += self.PAGE_SIZE
            pages_fetched += 1

            if pages_fetched % 10 == 0:
                print(f"  Fetched {pages_fetched} pages ({offset:,}/{total_count:,}), {len(cards)} Basel matches...")

            # Polite delay to avoid triggering Cloudflare
            time.sleep(0.3)

        # Save high-water mark
        self._state["max_pk"] = max_pk_this_run
        self._save_state()

        print(f"  Done: {pages_fetched} pages fetched, {len(cards)} Basel listings found")
        return cards

    def scrape_detail(self, page: Page, card: ListingCard) -> ListingDetail:
        """Build ListingDetail from stored API data (no network call needed)."""
        detail = ListingDetail(card=card)

        data = card.extras or self._listing_data.get(card.listing_id, {})
        if not data:
            return detail

        # Price
        detail.price_chf = data.get("rent_gross") or data.get("price_display")

        # Address
        parts = [data.get("street", ""), str(data.get("zipcode", "")), data.get("city", "")]
        addr = " ".join(p for p in parts if p).strip()
        detail.address = addr if addr else None

        # Full text for parser filters
        desc = data.get("description") or ""
        title = data.get("short_title") or ""
        detail.full_text = f"{title}\n{desc}"

        # Move-in date
        detail.move_in_date = data.get("moving_date")

        # Post date
        published = data.get("published") or data.get("created")
        if published:
            detail.post_date = published[:10]  # "2026-03-20T..." -> "2026-03-20"

        # Size
        surface = data.get("surface_living")
        if surface:
            detail.size_sqm = int(surface)

        # Furnished
        detail.furnished = data.get("is_furnished")

        # Raw attributes for parser fallback
        detail.raw_attributes = {
            "rooms": data.get("number_of_rooms"),
            "object_type": data.get("object_type"),
            "object_category": data.get("object_category"),
            "moving_date_type": data.get("moving_date_type"),
            "is_temporary": data.get("is_temporary"),
        }

        return detail

    # ── Internal helpers ──────────────────────────────────────────────

    def _api_get(self, params: dict, retries: int = 2) -> dict | None:
        """Make a GET request to the Flatfox API with retry on timeout."""
        for attempt in range(retries + 1):
            try:
                resp = requests.get(
                    self.API_URL,
                    params=params,
                    headers={"Accept": "application/json"},
                    timeout=20,
                )
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                if attempt < retries:
                    time.sleep(2)
                    continue
                print(f"  [WARN] Flatfox API error: {e}")
                return None

    def _matches_criteria(self, listing: dict) -> bool:
        """Client-side filter: Basel, rental, room/apartment, active, affordable."""
        # Must be in Basel
        zipcode = listing.get("zipcode")
        if not zipcode or int(zipcode) not in self.BASEL_ZIPCODES:
            return False

        # Must be rental
        if listing.get("offer_type") != "RENT":
            return False

        # Must be a relevant type
        cat = listing.get("object_category", "")
        obj_type = listing.get("object_type", "")
        if cat not in self.TARGET_CATEGORIES and obj_type not in self.TARGET_TYPES:
            return False

        # Must be active and not reserved
        if listing.get("status") != "act":
            return False
        if listing.get("reserved"):
            return False

        # Must have a price ("By request" = almost always expensive)
        price = listing.get("rent_gross") or listing.get("price_display")
        if not price or price > MAX_RENT_CHF:
            return False

        return True

    def _to_listing_card(self, listing: dict) -> ListingCard:
        """Convert API JSON to ListingCard."""
        pk = str(listing["pk"])
        title = listing.get("short_title") or listing.get("slug", "")
        url_path = listing.get("url", "")
        full_url = f"https://flatfox.ch{url_path}" if url_path else f"https://flatfox.ch/en/flat/{pk}/"

        # Build description from available fields
        desc_parts = []
        price = listing.get("rent_gross") or listing.get("price_display")
        if price:
            desc_parts.append(f"CHF {price}/mo")
        rooms = listing.get("number_of_rooms")
        if rooms:
            desc_parts.append(f"{rooms} rooms")
        surface = listing.get("surface_living")
        if surface:
            desc_parts.append(f"{surface}m2")
        city = listing.get("city", "")
        zipcode = listing.get("zipcode", "")
        if city:
            desc_parts.append(f"{zipcode} {city}")

        obj_type = listing.get("object_type", "")
        category = listing.get("object_category", "")
        cat_display = obj_type.replace("_", " ").title() if obj_type else category.title()

        return ListingCard(
            listing_id=pk,
            title=title,
            category=cat_display,
            description=" | ".join(desc_parts),
            url=full_url,
            source_site=self.name,
            extras=listing,
        )

    def _load_state(self) -> dict:
        """Load persistent state (high-water mark)."""
        if self.STATE_FILE.exists():
            with open(self.STATE_FILE, "r") as f:
                return json.load(f)
        return {}

    def _save_state(self) -> None:
        """Save persistent state."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.STATE_FILE, "w") as f:
            json.dump(self._state, f, indent=2)
