from playwright.sync_api import Page
from src.sites.base import BaseSite
from src.scraper import ListingCard, ListingDetail, _extract_attributes


class UnibasSite(BaseSite):
    name = "unibas"
    display_name = "markt.unibas.ch"
    base_url = "https://markt.unibas.ch/en/search/housing"

    SELECTORS = {
        "listing_card": "a[href*='/post/']",
        "card_grid": "div.grid.border-t",
        "load_more_button": "button.mx-auto.my-12",
        "detail_body": "article, main section, [class*='post'], [class*='detail']",
    }

    def apply_site_filters(self, page: Page) -> None:
        """Use the site's filter UI to select Type = Offers."""
        try:
            type_label = page.query_selector("label:has-text('Type')") or page.query_selector("label:has-text('Typ')")
            if not type_label:
                print("  [WARN] Could not find Type label")
                return

            type_root = type_label.evaluate_handle("el => el.closest('[class*=\"Select-root\"]') || el.parentElement")
            type_input = type_root.as_element().query_selector("input")
            if not type_input:
                print("  [WARN] Could not find Type input")
                return

            type_input.click()
            page.wait_for_timeout(800)

            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(300)
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)

            h1 = page.query_selector("h1")
            if h1:
                h1_text = h1.inner_text().strip()
                print(f"  Page heading: '{h1_text}'")
                if "Offer" in h1_text or "Angebot" in h1_text:
                    print("  Filter applied successfully")
                    return

            print("  [WARN] Could not confirm filter -- check browser")
        except Exception as e:
            print(f"  [WARN] Could not set Type filter: {e}")
            print("  Continuing without site-level filter")

    def scrape_cards(self, page: Page, known_ids: set[str] | None = None) -> list[ListingCard]:
        """Load the housing page and extract all listing cards."""
        print(f"Navigating to {self.display_name}...")
        page.goto(self.base_url, wait_until="networkidle")
        page.wait_for_timeout(3000)

        print("Applying site filters...")
        self.apply_site_filters(page)

        self._load_all_listings(page, known_ids=known_ids)

        card_elements = page.query_selector_all(self.SELECTORS["listing_card"])
        print(f"Found {len(card_elements)} listing cards")

        cards = []
        for el in card_elements:
            try:
                href = el.get_attribute("href") or ""
                if not href or "/post/" not in href:
                    continue

                listing_id = href.split("/")[-1]

                inner_text = el.inner_text().strip()
                lines = [l.strip() for l in inner_text.split("\n") if l.strip()]

                title = ""
                category = ""
                description = ""
                if len(lines) >= 2:
                    category = lines[0]
                    title = lines[1]
                    description = " ".join(lines[2:]) if len(lines) > 2 else ""
                elif len(lines) == 1:
                    title = lines[0]

                full_url = f"https://markt.unibas.ch{href}" if href.startswith("/") else href

                cards.append(ListingCard(
                    listing_id=listing_id,
                    title=title,
                    category=category,
                    description=description,
                    url=full_url,
                    source_site=self.name,
                ))
            except Exception as e:
                print(f"  [WARN] Failed to parse card: {e}")
                continue

        return cards

    def scrape_detail(self, page: Page, card: ListingCard) -> ListingDetail:
        """Navigate to a listing's detail page and extract full info."""
        detail = ListingDetail(card=card)

        try:
            page.goto(card.url, wait_until="networkidle")
            page.wait_for_timeout(2000)

            detail.full_text = page.inner_text("main") or page.inner_text("body")
            detail.raw_attributes = _extract_attributes(page)

        except Exception as e:
            print(f"  [WARN] Failed to load detail for '{card.title}': {e}")

        return detail

    def _load_all_listings(self, page: Page, max_clicks: int = 50, known_ids: set[str] | None = None) -> None:
        """Click 'Load more' button until all listings are loaded."""
        stale_attempts = 0

        for i in range(max_clicks):
            try:
                before_count = len(page.query_selector_all(self.SELECTORS["listing_card"]))

                if known_ids and i > 0:
                    card_els = page.query_selector_all(self.SELECTORS["listing_card"])
                    recent_ids = []
                    for el in card_els[-12:]:
                        href = el.get_attribute("href") or ""
                        if "/post/" in href:
                            recent_ids.append(href.split("/")[-1])
                    if recent_ids:
                        known_ratio = sum(1 for rid in recent_ids if rid in known_ids) / len(recent_ids)
                        if known_ratio >= 0.8:
                            print(f"  Reached known listings ({known_ratio:.0%} already seen), stopping ({before_count} cards)")
                            break

                btn = page.query_selector("button:has-text('Load more')")
                if not btn:
                    btn = page.query_selector("button:has-text('Mehr anzeigen')")
                if not btn:
                    btn = page.query_selector(self.SELECTORS["load_more_button"])
                if not btn or not btn.is_visible():
                    print(f"  All listings loaded ({before_count} cards, {i} clicks)")
                    break

                btn.scroll_into_view_if_needed()
                btn.click()
                page.wait_for_timeout(2500)

                after_count = len(page.query_selector_all(self.SELECTORS["listing_card"]))

                if after_count == before_count:
                    stale_attempts += 1
                    if stale_attempts >= 3:
                        print(f"  No new cards after {stale_attempts} attempts, stopping ({after_count} cards)")
                        break
                else:
                    stale_attempts = 0

                if (i + 1) % 10 == 0:
                    print(f"  Clicked 'Load more' {i + 1} times ({after_count} cards)...")

            except Exception:
                break
