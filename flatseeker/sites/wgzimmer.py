import re

from playwright.sync_api import Page

from flatseeker.scraper import ListingCard, ListingDetail
from flatseeker.sites.base import BaseSite


class WgzimmerSite(BaseSite):
    """wgzimmer.ch scraper -- the main Swiss WG room platform.

    Search requires Playwright (reCAPTCHA v3), but detail pages are plain HTTP.
    """

    name = "wgzimmer"
    display_name = "wgzimmer.ch"
    base_url = "https://www.wgzimmer.ch/en/wgzimmer/search/mate.html"

    # Search form values for Basel rooms under 700 CHF
    SEARCH_STATE = "baselstadt"
    PRICE_MAX = "700"

    SELECTORS = {
        "listing": "li.search-result-entry.search-mate-entry",
        "listing_link": "a",
        "post_date": ".create-date strong",
        "region": ".state .thumbState strong",
        "neighborhood": ".state .thumbState font",
        "available_from": ".from-date strong",
        "available_until": ".from-date font",
        "price": ".cost strong",
        "next_page": ".result-navigation a:last-child",
    }

    def apply_site_filters(self, page: Page) -> None:
        """Set search form values and submit via JavaScript (bypasses ad overlays)."""
        try:
            # Use JavaScript to set form values -- avoids ad overlay visibility issues
            page.evaluate(f"""
                document.querySelector('select[name="wgState"]').value = '{self.SEARCH_STATE}';
                document.querySelector('select[name="priceMax"]').value = '{self.PRICE_MAX}';
                var permAll = document.querySelector('input[name="permanent"][value="all"]');
                if (permAll) permAll.checked = true;
            """)
            page.wait_for_timeout(500)

            # Trigger search via the site's own JS function
            page.evaluate("submitForm()")
            page.wait_for_timeout(8000)  # Wait for reCAPTCHA v3 + page load

        except Exception as e:
            print(f"  [WARN] Failed to set search filters: {e}")

    def scrape_cards(self, page: Page, known_ids: set[str] | None = None) -> list[ListingCard]:
        """Load wgzimmer search results and extract listing cards."""
        print(f"Navigating to {self.display_name}...")
        page.goto(self.base_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)  # Extra time for reCAPTCHA JS to load

        # Handle cookie consent and ad overlays
        self._dismiss_cookies(page)
        self._dismiss_ad_overlays(page)

        print("Applying search filters...")
        self.apply_site_filters(page)

        # Collect cards from all pages (max 5 pages = ~120 listings, safety limit)
        all_cards = []
        page_num = 1
        MAX_PAGES = 5

        while page_num <= MAX_PAGES:
            cards = self._parse_results_page(page, page_num)
            if not cards:
                break
            all_cards.extend(cards)

            # Check for next page link and get its URL
            next_url = self._get_next_page_url(page)
            if not next_url:
                break

            # Navigate directly to next page (avoids ad overlay blocking clicks)
            page.goto(next_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            page_num += 1

        print(f"  Found {len(all_cards)} listings across {page_num} page(s)")
        return all_cards

    def scrape_detail(self, page: Page, card: ListingCard) -> ListingDetail:
        """Navigate to listing detail page and extract full info."""
        detail = ListingDetail(card=card)

        try:
            page.goto(card.url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Build full_text from relevant sections only (avoid footer boilerplate)
            text_parts = []
            for section_class in [
                ".date-cost",
                ".adress-region",
                ".person-content",
                ".room-content",
                ".mate-content",
            ]:
                section = page.query_selector(section_class)
                if section:
                    text_parts.append(section.inner_text())
            detail.full_text = (
                "\n".join(text_parts) if text_parts else page.inner_text("body")[:2000]
            )

            # Parse structured data from detail page sections
            detail.price_chf = self._parse_detail_price(page)
            detail.address = self._parse_detail_address(page)
            detail.move_in_date = self._parse_detail_date(page, "from")
            detail.post_date = card.extras.get("post_date")

        except Exception as e:
            print(f"  [WARN] Failed to load detail for '{card.title}': {e}")

        return detail

    # ── Internal helpers ──────────────────────────────────────────────

    def _dismiss_cookies(self, page: Page) -> None:
        """Dismiss cookie/consent dialogs (Google Fundingchoices / CMP)."""
        try:
            # Google Fundingchoices consent (fc-consent-root)
            # Try "Reject all" / "Do not consent" first (privacy-preserving)
            for selector in [
                ".fc-consent-root .fc-cta-do-not-consent",  # "Do not consent"
                ".fc-consent-root .fc-secondary-button",  # Secondary = reject
                ".fc-consent-root .fc-cta-consent",  # "Consent" as fallback
                ".fc-consent-root .fc-primary-button",  # Primary button
                "button:has-text('Reject all')",
                "button:has-text('Alle ablehnen')",
                "button:has-text('Accept all')",
                "button:has-text('Alle akzeptieren')",
            ]:
                btn = page.query_selector(selector)
                if btn and btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(2000)
                    print("  Dismissed cookie consent")
                    return
        except Exception:
            pass

    def _get_next_page_url(self, page: Page) -> str | None:
        """Get the URL for the next results page, or None if on last page."""
        nav = page.query_selector(".result-navigation")
        if not nav:
            return None
        links = nav.query_selector_all("a")
        for link in links:
            text = link.inner_text().strip().lower()
            if any(w in text for w in ["next", "weiter", ">"]):
                href = link.get_attribute("href")
                if href:
                    return f"https://www.wgzimmer.ch{href}" if href.startswith("/") else href
        return None

    def _dismiss_ad_overlays(self, page: Page) -> None:
        """Remove Google ad vignette overlays that block clicks."""
        try:
            page.evaluate(
                "document.querySelectorAll("
                "'ins.adsbygoogle-noablate, .fc-consent-root')"
                ".forEach(el => { if (el.style.position === 'fixed') el.remove(); });"
                "document.querySelectorAll('[data-vignette-loaded]')"
                ".forEach(el => el.remove());"
            )
            page.wait_for_timeout(500)
        except Exception:
            pass

    def _parse_results_page(self, page: Page, page_num: int) -> list[ListingCard]:
        """Extract listing cards from the current search results page."""
        listings = page.query_selector_all(self.SELECTORS["listing"])
        if not listings:
            print(f"  Page {page_num}: no listings found")
            return []

        cards = []
        for el in listings:
            try:
                card = self._parse_card_element(el)
                if card:
                    cards.append(card)
            except Exception as e:
                print(f"  [WARN] Failed to parse listing card: {e}")
                continue

        print(f"  Page {page_num}: {len(cards)} listings")
        return cards

    def _parse_card_element(self, el) -> ListingCard | None:
        """Parse a single listing card element into a ListingCard."""
        link = el.query_selector("a")
        if not link:
            return None

        href = link.get_attribute("href") or ""
        if not href or "/wglink/" not in href:
            return None

        # Extract listing ID from URL (the UUID part)
        parts = href.split("/")
        listing_id = ""
        for part in parts:
            # UUID pattern
            if len(part) == 36 and part.count("-") == 4:
                listing_id = part
                break
        if not listing_id:
            # Fallback: use last path segment
            listing_id = parts[-1].replace(".html", "") if parts else href

        full_url = f"https://www.wgzimmer.ch{href}" if href.startswith("/") else href

        # Extract card fields
        region = self._text(el, self.SELECTORS["region"])
        neighborhood_els = el.query_selector_all(".state .thumbState font")
        neighborhood = neighborhood_els[0].inner_text().strip() if neighborhood_els else ""

        available_from = self._text(el, self.SELECTORS["available_from"])
        available_until = self._text(el, self.SELECTORS["available_until"])
        price_text = self._text(el, self.SELECTORS["price"])
        post_date = self._text(el, self.SELECTORS["post_date"])

        # Build title and description
        title = f"WG room in {region}" if region else "WG room"
        if neighborhood:
            title += f" ({neighborhood})"

        desc_parts = []
        if price_text:
            desc_parts.append(f"CHF {price_text}/mo")
        if available_from:
            desc_parts.append(f"from {available_from}")
        if available_until:
            desc_parts.append(available_until)

        return ListingCard(
            listing_id=listing_id,
            title=title,
            category="WG Room",
            description=" | ".join(desc_parts),
            url=full_url,
            source_site=self.name,
            extras={
                "post_date": post_date,
                "available_from": available_from,
                "available_until": available_until,
                "price_text": price_text,
                "region": region,
                "neighborhood": neighborhood,
            },
        )

    def _parse_detail_price(self, page: Page) -> int | None:
        """Extract rent from detail page."""
        try:
            date_cost = page.query_selector(".date-cost")
            if not date_cost:
                return None
            text = date_cost.inner_text()
            # Match patterns like "sFr. 480 .--" or "CHF 480" or just "480"
            match = re.search(r"(?:sFr\.|CHF)?\s*(\d[\d\s]*)", text)
            if match:
                return int(match.group(1).replace(" ", ""))
        except Exception:
            pass
        return None

    def _parse_detail_address(self, page: Page) -> str | None:
        """Extract address from detail page."""
        try:
            addr_section = page.query_selector(".adress-region")
            if not addr_section:
                return None

            paragraphs = addr_section.query_selector_all("p")
            street = ""
            city = ""
            for p in paragraphs:
                strong = p.query_selector("strong")
                if not strong:
                    continue
                label = strong.inner_text().strip().lower()
                # Get text after the strong tag
                full_text = p.inner_text().strip()
                value = full_text.replace(strong.inner_text(), "").strip()

                if "adresse" in label or "address" in label:
                    street = value
                elif "ort" in label or "city" in label or "plz" in label:
                    city = value

            if street and city:
                return f"{street}, {city}"
            return street or city or None
        except Exception:
            return None

    def _parse_detail_date(self, page: Page, which: str = "from") -> str | None:
        """Extract move-in date from detail page."""
        try:
            date_section = page.query_selector(".date-cost")
            if not date_section:
                return None
            paragraphs = date_section.query_selector_all("p")
            for p in paragraphs:
                strong = p.query_selector("strong")
                if not strong:
                    continue
                label = strong.inner_text().strip().lower()
                if which == "from" and ("ab dem" in label or "from" in label):
                    full_text = p.inner_text().strip()
                    return full_text.replace(strong.inner_text(), "").strip()
        except Exception:
            pass
        return None

    def _text(self, parent, selector: str) -> str:
        """Safely extract text from a child element."""
        el = parent.query_selector(selector)
        return el.inner_text().strip() if el else ""
