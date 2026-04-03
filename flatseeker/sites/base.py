from abc import ABC, abstractmethod
from playwright.sync_api import Page
from flatseeker.scraper import ListingCard, ListingDetail


class BaseSite(ABC):
    """Abstract base for all housing site scrapers."""

    name: str = ""            # e.g. "unibas"
    display_name: str = ""    # e.g. "markt.unibas.ch"
    base_url: str = ""

    def apply_site_filters(self, page: Page) -> None:
        """Optional: use the site's UI to set filters before scraping."""
        pass

    @abstractmethod
    def scrape_cards(self, page: Page, known_ids: set[str] | None = None) -> list[ListingCard]:
        """Load the site and extract all listing cards."""
        ...

    @abstractmethod
    def scrape_detail(self, page: Page, card: ListingCard) -> ListingDetail:
        """Navigate to a listing's detail page and extract full info."""
        ...
