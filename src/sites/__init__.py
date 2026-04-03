from src.sites.base import BaseSite
from src.sites.unibas import UnibasSite
from src.sites.flatfox import FlatfoxSite
from src.sites.wgzimmer import WgzimmerSite

SITE_REGISTRY: dict[str, type[BaseSite]] = {
    "unibas": UnibasSite,
    "flatfox": FlatfoxSite,
    "wgzimmer": WgzimmerSite,
}

ENABLED_SITES: list[str] = ["unibas", "flatfox", "wgzimmer"]


def get_enabled_sites(names: list[str] | None = None) -> list[BaseSite]:
    """Return instantiated site objects for the given names (or all enabled)."""
    use = names or ENABLED_SITES
    sites = []
    for name in use:
        cls = SITE_REGISTRY.get(name)
        if cls is None:
            print(f"[WARN] Unknown site: {name}")
            continue
        sites.append(cls())
    return sites
