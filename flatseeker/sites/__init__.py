from flatseeker.sites.base import BaseSite
from flatseeker.sites.unibas import UnibasSite
from flatseeker.sites.flatfox import FlatfoxSite
from flatseeker.sites.wgzimmer import WgzimmerSite

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
