import re
from datetime import date


def parse_price(text: str) -> int | None:
    """Extract monthly rent in CHF from German/English text."""
    if not text:
        return None

    patterns = [
        r'(\d[\d\'\.]*)\s*(?:CHF|Fr\.|Franken|SFr)',
        r'(?:CHF|Fr\.|SFr)[\s.:]*(\d[\d\'\.]*)',
        r'(\d[\d\'\.]*)\s*[.-]*/\s*(?:Mt|Monat|month)',
        r'(?:Miete|Rent|Price|Preis)[:\s]*(\d[\d\'\.]*)',
        r'(\d{3,4})\s*(?:pro Monat|per month|mtl|monatlich)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            price_str = match.group(1).replace("'", "").replace(".", "")
            try:
                price = int(price_str)
                if 100 <= price <= 5000:
                    return price
            except ValueError:
                continue

    # Fallback: look for any 3-4 digit number near money-related words
    money_context = re.search(
        r'(?:CHF|Fr|Miete|rent|price|preis|kosten)[\s\S]{0,20}?(\d{3,4})',
        text, re.IGNORECASE
    )
    if money_context:
        price = int(money_context.group(1))
        if 100 <= price <= 5000:
            return price

    return None


def parse_roommate_count(text: str) -> int | None:
    """Extract total number of people in WG. Returns None if not a WG."""
    if not text:
        return None

    patterns = [
        r'(\d)er[\s-]?WG',                          # "3er WG" -> 3
        r'(\d)[\s-]?(?:Personen|person)[\s-]?WG',   # "3-Personen-WG"
        r'WG\s*(?:mit|with)\s*(\d)\s*(?:Personen|person|Leute|people)',
        r'(\d)\s*(?:Mitbewohner|roommate)',          # "2 Mitbewohner" -> 2+1=3
        r'(\d)\s*(?:Zi|Zimmer)[\s,]*WG',            # "4 Zi WG"
    ]

    for i, pattern in enumerate(patterns):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            num = int(match.group(1))
            if i == 3:  # Mitbewohner pattern
                return num + 1
            return num

    return None


def parse_move_in_date(text: str) -> date | None:
    """Extract move-in date from German/English text."""
    if not text:
        return None

    if re.search(r'ab sofort|per sofort|immediately|asap|ab jetzt', text, re.IGNORECASE):
        return date.today()

    # German date: DD.MM.YYYY or DD.MM.YY
    match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})', text)
    if match:
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            pass

    months_de = {
        'januar': 1, 'februar': 2, 'märz': 3, 'april': 4,
        'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
        'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12,
    }
    months_en = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
    }
    all_months = {**months_de, **months_en}

    month_pattern = '|'.join(all_months.keys())
    match = re.search(
        rf'(?:ab|from|per|starting)\s+(?:(\d{{1,2}})\.\s*)?({month_pattern})\s*(\d{{4}})?',
        text, re.IGNORECASE
    )
    if match:
        day = int(match.group(1)) if match.group(1) else 1
        month_name = match.group(2).lower()
        month = all_months.get(month_name)
        year = int(match.group(3)) if match.group(3) else date.today().year
        if month:
            try:
                return date(year, month, day)
            except ValueError:
                pass

    return None


def parse_post_date(text: str) -> date | None:
    """Extract the posting date from a detail page.

    The site shows dates like '17.03.2026' near the top of the listing.
    We look for DD.MM.YYYY dates that are NOT part of move-in context.
    """
    if not text:
        return None

    # Look for standalone DD.MM.YYYY dates (the post date is typically
    # one of the first dates on the page, not preceded by move-in keywords)
    for match in re.finditer(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', text):
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            d = date(year, month, day)
            # Post dates should be in the past or today, and recent (within 1 year)
            if d <= date.today() and (date.today() - d).days < 365:
                return d
        except ValueError:
            continue

    return None


def parse_location(text: str) -> str | None:
    """Extract location -- street address or neighborhood in Basel."""
    if not text:
        return None

    # Strategy 1: Full street address (Streetname + number)
    match = re.search(
        r'([A-Z\u00C0-\u00FF][a-z\u00E0-\u00FF]+(?:strasse|str\.|weg|gasse|platz|ring|graben|allee|rain|matte|pfad)\s*\d+[a-z]?)[\s,]*(\d{4}\s*\w+)?',
        text
    )
    if match:
        addr = match.group(1).strip()
        plz_city = match.group(2)
        if plz_city:
            addr += ", " + plz_city.strip()
        elif "Basel" not in addr:
            addr += ", Basel"
        return addr

    # Strategy 2: PLZ + Basel
    match = re.search(r'(\d{4})\s*(Basel)', text)
    if match:
        return f"{match.group(1)} {match.group(2)}"

    # Check for non-Swiss locations first (exclude France/Germany)
    non_swiss = ["saint-louis", "saint louis", "st-louis", "huningue", "hésingue",
                 "weil am rhein", "lörrach", "grenzach", "rheinfelden de"]
    text_lower = text.lower()
    for loc in non_swiss:
        if loc in text_lower:
            return None  # Not in Switzerland, skip

    # Strategy 3: Known Basel-area neighborhoods
    neighborhoods = [
        "St. Johann", "St Johann", "Sankt Johann",
        "Gundeldingen", "Gundeli",
        "Kleinbasel", "Klybeck", "Kleinhüningen",
        "Matthäus", "Clara", "Wettstein", "Hirzbrunnen",
        "Rosental", "Iselin", "Bruderholz", "Bachletten",
        "Gotthelf", "Altstadt Grossbasel", "Altstadt Kleinbasel",
        "Am Ring", "Breite", "Vorstädte",
        "Spalen", "Kannenfeld",
        "Riehen", "Bettingen", "Binningen", "Allschwil",
        "Münchenstein", "Muttenz", "Pratteln", "Reinach",
        "Birsfelden", "Bottmingen", "Oberwil",
        "Liestal", "Aesch", "Arlesheim", "Dornach",
        "Dreispitz",
    ]

    for hood in neighborhoods:
        if hood.lower() in text_lower:
            return f"{hood}, Basel, Switzerland"

    return None


def is_not_housing(text: str) -> bool:
    """Detect listings that are not actual housing (cleaning, furniture, offices, etc.)."""
    text_lower = text.lower()

    # Non-housing keywords -- if ANY appears in title or first 300 chars, reject
    junk_keywords = [
        "reinigung", "grundputz", "putzfrau", "cleaning service",
        "regal ", "möbel ", "sofa ", "tisch ", "furniture",
        "kunstraum", "pop-up", "popup",
        "zusatzverdienst", "nebenjob", "verdienst",
        "praxisraum", "praxis-", "büroraum", "buroraum",
        "atelierraum", "hobbyraum", "lagerraum", "kellerraum",
        "parkplatz", "garagenplatz", "einstellhalle",
        "coworking", "co-working",
    ]
    check = text_lower[:500]
    return any(kw in check for kw in junk_keywords)


def is_sublet(text: str) -> bool:
    """Detect short-term sublets / Zwischenmiete.

    We want permanent housing (1+ year). Reject:
    - Explicit Zwischenmiete/sublet/subrent/Untermiete with end dates
    - Very short date ranges (less than ~2 months)
    """
    text_lower = text.lower()
    check = text_lower[:800]

    # Explicit sublet keywords
    sublet_keywords = [
        "zwischenmiete", "sublet", "subrent", "sous-location",
        "temporary", "temporär",
    ]
    if any(kw in check for kw in sublet_keywords):
        return True

    # "befristet" but NOT "unbefristet" (which means permanent/unlimited)
    if re.search(r'(?<!un)befristet', check):
        return True

    # "Untermiete" with a clear end date signals a short sublet
    if "untermiete" in check:
        # Check if there's an end date pattern like "bis", "until", "-"
        if re.search(r'untermiete.*(?:bis|until|[-–].*\d{1,2}\.\d{1,2})', check):
            return True
        # "Untermiete" with month range like "April-Juni", "März und April"
        if re.search(r'untermiete.*(?:januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember).*(?:[-–&und]|bis).*(?:januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)', check):
            return True

    # Short date ranges in title: "28 Mar - 6 April", "15. April - 10. Juni"
    # These indicate sublets even without the keyword
    if re.search(r'\d{1,2}\.?\s*(?:jan|feb|mär|mar|apr|mai|may|jun|jul|aug|sep|okt|oct|nov|dez|dec)\w*\s*[-–]\s*\d{1,2}\.?\s*(?:jan|feb|mär|mar|apr|mai|may|jun|jul|aug|sep|okt|oct|nov|dez|dec)', check):
        return True

    return False


def is_foreign_location(text: str) -> bool:
    """Detect listings that are in Germany, France, or other non-Swiss locations."""
    text_lower = text.lower()

    foreign_markers = [
        # German cities/regions near Basel
        "lörrach", "lorrach", "grenzach", "wyhlen", "grenzach-wyhlen",
        "weil am rhein", "rheinfelden (de)", "rheinfelden (d)",
        "schopfheim", "bad säckingen",
        # French cities near Basel
        "saint-louis", "saint louis", "st-louis", "huningue",
        "hésingue", "hesingue", "bartenheim",
        # Other countries
        "berlin", "münchen", "munich", "frankfurt", "hamburg",
        "paris", "lyon", "strasbourg",
        # Explicit Germany/France markers
        "(d)", "(de)", "(f)", "(fr)",
        "deutschland", "germany", "frankreich", "france",
    ]

    for marker in foreign_markers:
        if marker in text_lower:
            # Make sure "(d)" and "(de)" are not matching random words
            if marker in ("(d)", "(de)", "(f)", "(fr)"):
                if re.search(r'\b' + re.escape(marker) + r'\b', text_lower):
                    return True
            else:
                return True

    # EUR currency = almost certainly Germany
    if re.search(r'\b(?:euro|eur|€)\b', text_lower, re.IGNORECASE):
        return True

    return False


def is_request_not_offer(text: str) -> bool:
    """Detect if a listing is someone LOOKING for housing (not offering).

    Important: "Nachmieter gesucht" (successor tenant wanted) = OFFER (they have a place)
    "Suchen Mitbewohner/in" (looking for roommate) = OFFER (they have a room)
    "Ich suche ein Zimmer" (I'm looking for a room) = REQUEST (they need a place)
    """
    check_text = text[:500].lower()

    # These are OFFERS even though they contain "suche/gesucht"
    offer_patterns = [
        r'nachmieter.*gesucht', r'nachmieterin.*gesucht',
        r'mitbewohner.*gesucht', r'mitbewohnerin.*gesucht',
        r'suchen.*mitbewohner', r'suchen.*nachmieter',
        r'wir suchen.*für unsere', r'suchen.*für.*wg',
        r'zu vermieten', r'to rent', r'for rent',
    ]
    if any(re.search(p, check_text) for p in offer_patterns):
        return False

    # These are actual REQUESTS (someone looking for a place)
    request_patterns = [
        r'\bich suche\b',
        r'\bsuche\s+(ein|1|eine|einen)\s+(zimmer|wohnung|room|apartment|wg)',
        r'\bsuchen\s+(eine?n?\s+)?(zimmer|wohnung|room|apartment)',
        r'\blooking for\s+(a\s+)?(room|flat|apartment|place)',
        r'\bsearching for\b',
    ]
    return any(re.search(p, check_text) for p in request_patterns)


def has_incompatible_requirements(text: str) -> bool:
    """Detect WGs with lifestyle/identity requirements that don't match.

    Only catches explicit household requirements or expectations,
    not casual self-descriptions.
    """
    check = text[:800].lower()

    # Pronoun requirements (must be in a "requirement" context)
    pronoun_phrases = [
        "they/them", "pronoun", "pronouns",
    ]
    if any(p in check for p in pronoun_phrases):
        return True

    # Vegan household requirements (not just "I'm vegan" self-description)
    vegan_requirement_patterns = [
        r'vegan(?:e[rn]?)?\s+(?:haushalt|household|wg|leben|lifestyle|küche|kitchen)',
        r'(?:must|should|need to|sollte|muss)\s+be\s+vegan',
        r'(?:nur|only|strictly)\s+vegan',
        r'wir\s+(?:leben|sind|are)\s+(?:alle\s+)?vegan',
        r'vegan(?:e[rn]?)?\s+(?:ernährung|diet)\s+(?:ist|is)\s+(?:pflicht|required|must)',
        r'(?:expecting|erwarten|expect)\s+.*vegan',
    ]
    if any(re.search(p, check) for p in vegan_requirement_patterns):
        return True

    return False
