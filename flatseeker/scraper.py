from dataclasses import dataclass, field

from playwright.sync_api import Page, sync_playwright

from flatseeker.config import HEADLESS


@dataclass
class ListingCard:
    listing_id: str
    title: str
    category: str
    description: str
    url: str
    source_site: str = ""
    extras: dict = field(default_factory=dict)


@dataclass
class ListingDetail:
    card: ListingCard
    full_text: str = ""
    price_chf: int | None = None
    address: str | None = None
    num_people: int | None = None
    move_in_date: str | None = None
    furnished: bool | None = None
    size_sqm: int | None = None
    transit_min: int | None = None
    post_date: str | None = None
    days_since_post: int | None = None
    raw_attributes: dict = field(default_factory=dict)


def _extract_attributes(page: Page) -> dict:
    """Try to extract structured key-value attributes from a detail page."""
    attrs = {}

    try:
        dts = page.query_selector_all("dt")
        dds = page.query_selector_all("dd")
        for dt, dd in zip(dts, dds):
            key = dt.inner_text().strip()
            val = dd.inner_text().strip()
            if key and val:
                attrs[key] = val

        labels = page.query_selector_all("[class*='label'], [class*='Label']")
        for label in labels:
            key = label.inner_text().strip().rstrip(":")
            sibling = label.evaluate("el => el.nextElementSibling?.innerText")
            if key and sibling:
                attrs[key] = sibling.strip()

        rows = page.query_selector_all("tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                key = cells[0].inner_text().strip()
                val = cells[1].inner_text().strip()
                if key and val:
                    attrs[key] = val

    except Exception:
        pass

    return attrs


def create_browser(headless: bool = None) -> tuple:
    """Create and return (playwright, browser/context, page) tuple.

    Uses a persistent browser context (saved profile) so that reCAPTCHA v3
    builds up trust over time and doesn't block automated searches.
    """
    if headless is None:
        headless = HEADLESS

    from flatseeker.config import DATA_DIR

    profile_dir = str((DATA_DIR / "browser_profile").resolve())

    pw = sync_playwright().start()
    context = pw.chromium.launch_persistent_context(
        profile_dir,
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
        viewport={"width": 1280, "height": 800},
    )
    page = context.pages[0] if context.pages else context.new_page()
    # Hide webdriver flag from reCAPTCHA detection
    page.add_init_script('Object.defineProperty(navigator, "webdriver", {get: () => false})')
    return pw, context, page


def close_browser(pw, browser) -> None:
    browser.close()
    pw.stop()
