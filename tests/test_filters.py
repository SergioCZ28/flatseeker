"""Unit tests for flatseeker.filters -- pass1 and pass2 filter logic."""

from flatseeker.filters import pass1_card_filter, pass2_detail_filter
from flatseeker.scraper import ListingCard, ListingDetail


def _make_card(
    listing_id="test-001",
    title="Nice room in 3er WG",
    category="Shared room",
    description="480 CHF, Gundeli",
    url="https://example.com/test",
    source_site="test",
) -> ListingCard:
    return ListingCard(
        listing_id=listing_id,
        title=title,
        category=category,
        description=description,
        url=url,
        source_site=source_site,
    )


def _make_detail(card: ListingCard = None, full_text: str = "") -> ListingDetail:
    if card is None:
        card = _make_card()
    return ListingDetail(card=card, full_text=full_text)


# ── pass1_card_filter ────────────────────────────────────────────────────────


class TestPass1CardFilter:
    def test_normal_listing_passes(self):
        cards = [_make_card()]
        result = pass1_card_filter(cards, {})
        assert len(result) == 1

    def test_already_seen_skipped(self):
        card = _make_card(listing_id="seen-001")
        cache = {"seen-001": {"status": "rejected_price"}}
        result = pass1_card_filter([card], cache)
        assert len(result) == 0

    def test_workspace_category_rejected(self):
        card = _make_card(category="Workspace")
        result = pass1_card_filter([card], {})
        assert len(result) == 0

    def test_5plus_room_rejected(self):
        card = _make_card(category="5+ room apartment")
        result = pass1_card_filter([card], {})
        assert len(result) == 0

    def test_cleaning_ad_rejected(self):
        card = _make_card(title="Reinigung gesucht", description="Putzfrau für WG")
        result = pass1_card_filter([card], {})
        assert len(result) == 0

    def test_request_rejected(self):
        card = _make_card(title="Ich suche ein Zimmer in Basel")
        result = pass1_card_filter([card], {})
        assert len(result) == 0

    def test_sublet_rejected(self):
        card = _make_card(title="Zwischenmiete Juni-August")
        result = pass1_card_filter([card], {})
        assert len(result) == 0

    def test_foreign_rejected(self):
        card = _make_card(title="Room in Lörrach", description="400 EUR/month")
        result = pass1_card_filter([card], {})
        assert len(result) == 0

    def test_too_expensive_rejected(self):
        card = _make_card(description="Rent: 1200 CHF/month")
        result = pass1_card_filter([card], {})
        assert len(result) == 0

    def test_no_price_passes(self):
        card = _make_card(description="Beautiful room, great location")
        result = pass1_card_filter([card], {})
        assert len(result) == 1


# ── pass2_detail_filter ──────────────────────────────────────────────────────


class TestPass2DetailFilter:
    def test_normal_detail_passes(self):
        detail = _make_detail(full_text="Zimmer in 3er WG, 480 CHF, Gundeldingen")
        result = pass2_detail_filter([detail], {})
        assert len(result) == 1

    def test_too_expensive_rejected(self):
        detail = _make_detail(full_text="Beautiful room, Miete: 900 CHF pro Monat")
        result = pass2_detail_filter([detail], {})
        assert len(result) == 0

    def test_too_many_roommates_rejected(self):
        detail = _make_detail(full_text="Room in 6er WG, 400 CHF")
        result = pass2_detail_filter([detail], {})
        assert len(result) == 0

    def test_sublet_in_detail_rejected(self):
        detail = _make_detail(full_text="Zwischenmiete, schönes Zimmer, 500 CHF")
        result = pass2_detail_filter([detail], {})
        assert len(result) == 0

    def test_foreign_in_detail_rejected(self):
        detail = _make_detail(full_text="Nice room in Lörrach, 400 EUR")
        result = pass2_detail_filter([detail], {})
        assert len(result) == 0

    def test_duplicate_title_rejected(self):
        card1 = _make_card(listing_id="dup-001", title="Same Title")
        card2 = _make_card(listing_id="dup-002", title="Same Title")
        d1 = _make_detail(card=card1, full_text="Room details")
        d2 = _make_detail(card=card2, full_text="Room details")
        result = pass2_detail_filter([d1, d2], {})
        assert len(result) == 1

    def test_incompatible_requirements_rejected(self):
        detail = _make_detail(full_text="Wir leben in einer veganen WG, 500 CHF")
        result = pass2_detail_filter([detail], {})
        assert len(result) == 0
