"""Unit tests for flatseeker.parser -- text extraction functions."""
from datetime import date
from flatseeker.parser import (
    parse_price,
    parse_roommate_count,
    parse_move_in_date,
    parse_location,
    parse_post_date,
    is_not_housing,
    is_sublet,
    is_foreign_location,
    is_request_not_offer,
    has_incompatible_requirements,
)


# ── parse_price ──────────────────────────────────────────────────────────────

class TestParsePrice:
    def test_chf_after_number(self):
        assert parse_price("480 CHF pro Monat") == 480

    def test_chf_before_number(self):
        assert parse_price("CHF 650") == 650

    def test_fr_format(self):
        assert parse_price("Fr. 550.-") == 550

    def test_sfr_format(self):
        assert parse_price("SFr 480") == 480

    def test_with_apostrophe_separator(self):
        assert parse_price("1'200 CHF") == 1200

    def test_miete_keyword(self):
        assert parse_price("Miete: 700") == 700

    def test_per_month(self):
        assert parse_price("480 pro Monat") == 480

    def test_no_price(self):
        assert parse_price("Nice room in Basel") is None

    def test_empty(self):
        assert parse_price("") is None

    def test_none(self):
        assert parse_price(None) is None

    def test_too_high_ignored(self):
        assert parse_price("Price: 9999 CHF") is None

    def test_too_low_ignored(self):
        assert parse_price("CHF 50") is None


# ── parse_roommate_count ─────────────────────────────────────────────────────

class TestParseRoommateCount:
    def test_3er_wg(self):
        assert parse_roommate_count("3er WG") == 3

    def test_4er_wg(self):
        assert parse_roommate_count("4er-WG in Gundeli") == 4

    def test_mitbewohner_adds_one(self):
        assert parse_roommate_count("2 Mitbewohner") == 3

    def test_personen_wg(self):
        assert parse_roommate_count("3-Personen-WG") == 3

    def test_no_wg_info(self):
        assert parse_roommate_count("Schönes Zimmer") is None

    def test_none(self):
        assert parse_roommate_count(None) is None


# ── parse_move_in_date ───────────────────────────────────────────────────────

class TestParseMoveInDate:
    def test_ab_sofort(self):
        assert parse_move_in_date("ab sofort verfügbar") == date.today()

    def test_immediately(self):
        assert parse_move_in_date("Available immediately") == date.today()

    def test_german_date(self):
        assert parse_move_in_date("Einzug ab 01.06.2026") == date(2026, 6, 1)

    def test_month_name_german(self):
        assert parse_move_in_date("ab Juni 2026") == date(2026, 6, 1)

    def test_month_name_english(self):
        assert parse_move_in_date("from July 2026") == date(2026, 7, 1)

    def test_no_date(self):
        assert parse_move_in_date("Nice room available") is None


# ── parse_location ───────────────────────────────────────────────────────────

class TestParseLocation:
    def test_street_address(self):
        result = parse_location("Wohnung an der Feldbergstrasse 42, 4057 Basel")
        assert result is not None
        assert "Feldbergstrasse 42" in result

    def test_plz_basel(self):
        assert parse_location("4052 Basel") == "4052 Basel"

    def test_neighborhood(self):
        result = parse_location("WG in Gundeldingen")
        assert result is not None
        assert "Gundeldingen" in result

    def test_foreign_returns_none(self):
        assert parse_location("Wohnung in Saint-Louis") is None

    def test_no_location(self):
        assert parse_location("Schönes Zimmer frei") is None


# ── parse_post_date ──────────────────────────────────────────────────────────

class TestParsePostDate:
    def test_valid_date(self):
        result = parse_post_date("Erstellt am 15.03.2026")
        assert result == date(2026, 3, 15)

    def test_future_date_ignored(self):
        assert parse_post_date("Verfügbar ab 01.01.2099") is None

    def test_no_date(self):
        assert parse_post_date("Schönes Zimmer") is None


# ── is_not_housing ───────────────────────────────────────────────────────────

class TestIsNotHousing:
    def test_cleaning(self):
        assert is_not_housing("Reinigung gesucht") is True

    def test_furniture(self):
        assert is_not_housing("Sofa zu verkaufen") is True

    def test_parking(self):
        assert is_not_housing("Parkplatz zu vermieten") is True

    def test_coworking(self):
        assert is_not_housing("Coworking Space Basel") is True

    def test_actual_housing(self):
        assert is_not_housing("Zimmer in 3er WG frei") is False


# ── is_sublet ────────────────────────────────────────────────────────────────

class TestIsSublet:
    def test_zwischenmiete(self):
        assert is_sublet("Zwischenmiete Juni-August") is True

    def test_sublet_english(self):
        assert is_sublet("Sublet available for summer") is True

    def test_temporary(self):
        assert is_sublet("Temporary room available") is True

    def test_befristet(self):
        assert is_sublet("Zimmer befristet zu vermieten") is True

    def test_unbefristet_is_not_sublet(self):
        assert is_sublet("Zimmer unbefristet") is False

    def test_permanent_housing(self):
        assert is_sublet("Zimmer in 3er WG ab Juni") is False

    def test_date_range_in_title(self):
        assert is_sublet("Room 15. April - 10. Juni") is True


# ── is_foreign_location ──────────────────────────────────────────────────────

class TestIsForeignLocation:
    def test_lorrach(self):
        assert is_foreign_location("Wohnung in Lörrach") is True

    def test_saint_louis(self):
        assert is_foreign_location("Room in Saint-Louis") is True

    def test_saint_louis_no_dash(self):
        assert is_foreign_location("Room in Saint Louis") is True

    def test_euro_currency(self):
        assert is_foreign_location("Miete: 400 EUR") is True

    def test_weil_am_rhein(self):
        assert is_foreign_location("Weil am Rhein, nice flat") is True

    def test_basel_is_fine(self):
        assert is_foreign_location("Room in Basel, Gundeli") is False


# ── is_request_not_offer ─────────────────────────────────────────────────────

class TestIsRequestNotOffer:
    def test_ich_suche(self):
        assert is_request_not_offer("Ich suche ein Zimmer in Basel") is True

    def test_looking_for(self):
        assert is_request_not_offer("Looking for a room in Basel") is True

    def test_nachmieter_gesucht_is_offer(self):
        assert is_request_not_offer("Nachmieter gesucht ab Juni") is False

    def test_zu_vermieten_is_offer(self):
        assert is_request_not_offer("Zimmer zu vermieten") is False

    def test_mitbewohner_gesucht_is_offer(self):
        assert is_request_not_offer("Mitbewohnerin gesucht für WG") is False

    def test_neutral_text(self):
        assert is_request_not_offer("Schönes Zimmer in Basel") is False


# ── has_incompatible_requirements ────────────────────────────────────────────

class TestHasIncompatibleRequirements:
    def test_pronoun_requirement(self):
        assert has_incompatible_requirements("Please share your pronouns") is True

    def test_vegan_household(self):
        assert has_incompatible_requirements("Wir leben in einer veganen WG") is True

    def test_no_requirements(self):
        assert has_incompatible_requirements("Nice room in Basel, all welcome") is False
