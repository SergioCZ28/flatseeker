"""
Flatseeker - main entry point.

Usage:
    flatseeker                       # full run (headless)
    flatseeker --no-headless         # visible browser (debugging)
    flatseeker --skip-maps           # skip Google Maps API calls
    flatseeker --force-refresh       # ignore cache, re-process all
    flatseeker --limit 5             # only process first N new listings (testing)
    flatseeker --sites unibas        # only scrape specific sites
"""

import argparse
import io
import sys

# Fix Windows console encoding for emoji/unicode in listing titles
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="ignore")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="ignore")

from flatseeker import config  # noqa: E402
from flatseeker.cache import load_cache, make_cache_id, save_cache  # noqa: E402
from flatseeker.filters import (  # noqa: E402
    pass1_card_filter,
    pass2_detail_filter,
    pass3_transit_filter,
)
from flatseeker.report import generate_html_report, print_console_report  # noqa: E402
from flatseeker.scraper import close_browser, create_browser  # noqa: E402
from flatseeker.sites import get_enabled_sites  # noqa: E402


def _check_results() -> int:
    """Show cache breakdown and matched listings."""
    from collections import Counter

    cache = load_cache()
    listings = {k: v for k, v in cache.items() if isinstance(v, dict) and "status" in v}
    statuses = Counter(v["status"] for v in listings.values())

    print("=== Filter breakdown ===")
    for status, count in statuses.most_common():
        print(f"  {status:30s} {count}")

    matches = [v for v in listings.values() if v["status"].startswith("matched")]
    print(f"\n=== {len(matches)} Matched listings ===\n")
    for i, v in enumerate(sorted(matches, key=lambda x: x.get("price") or 9999), 1):
        price = v.get("price", "?")
        transit = v.get("transit_min", "?")
        post = v.get("post_date", "?")
        title = v["title"][:60]
        addr = v.get("address", "no addr")
        if addr and len(addr) > 25:
            addr = addr[:25]
        print(
            f"{i:2}. {str(price):>4} CHF | {str(transit):>3} min "
            f"| {str(post):>10} | {addr:25s} | {title}"
        )

    return 0


def main():
    parser = argparse.ArgumentParser(description="Flatseeker - Basel WG room scanner")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    parser.add_argument("--skip-maps", action="store_true", help="Skip Google Maps API calls")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cache, reprocess all")
    parser.add_argument(
        "--limit", type=int, default=0, help="Limit new listings to process (for testing)"
    )
    parser.add_argument(
        "--sites", type=str, default="", help="Comma-separated list of sites to scan (default: all)"
    )
    parser.add_argument(
        "--check-results",
        action="store_true",
        help="Show cache breakdown and matched listings, then exit",
    )
    args = parser.parse_args()

    if args.check_results:
        return _check_results()

    if args.no_headless:
        config.HEADLESS = False

    # Load cache
    cache = load_cache()
    if args.force_refresh:
        cache = {}
        print("Cache cleared (force refresh mode)")

    # Resolve sites
    site_names = [s.strip() for s in args.sites.split(",") if s.strip()] if args.sites else None
    sites = get_enabled_sites(site_names)
    if not sites:
        print("No valid sites to scan.")
        return 1

    print("=" * 60)
    print("  Flatseeker")
    print(f"  Sites: {', '.join(s.display_name for s in sites)}")
    print("=" * 60)

    # Start browser
    pw, browser, page = create_browser(headless=config.HEADLESS)

    all_matched = []
    total_cards = 0
    total_pass1 = 0
    total_pass2 = 0

    try:
        for site in sites:
            print(f"\n{'─' * 50}")
            print(f"  Scanning: {site.display_name}")
            print(f"{'─' * 50}")

            # Step 1: Scrape listing cards
            # Build known_ids as raw slugs (without site prefix) for early-stop detection
            prefix = f"{site.name}:"
            known_ids = {k[len(prefix) :] for k in cache if k.startswith(prefix)} if cache else None
            n_known = len(known_ids or set())
            print(f"\n[1/5] Scraping listing cards... ({n_known} known for {site.name})")
            cards = site.scrape_cards(page, known_ids=known_ids)

            # Prefix listing IDs with site name for cache
            for card in cards:
                card.listing_id = make_cache_id(site.name, card.listing_id)

            site_total = len(cards)
            total_cards += site_total
            print(f"  Found {site_total} total listings")

            # Step 2: First-pass filter (card level)
            print("\n[2/5] Pass 1: Card-level filtering...")
            candidates = pass1_card_filter(cards, cache)
            print(f"  {len(candidates)} new listings passed card filter")

            if args.limit and len(candidates) > args.limit:
                candidates = candidates[: args.limit]
                print(f"  Limited to {args.limit} for testing")

            total_pass1 += len(candidates)

            # Step 3: Scrape detail pages
            print(f"\n[3/5] Scraping {len(candidates)} detail pages...")
            details = []
            for i, card in enumerate(candidates):
                print(f"  [{i + 1}/{len(candidates)}] {card.title[:50]}...")
                detail = site.scrape_detail(page, card)
                details.append(detail)

            # Step 4: Second-pass filter (detail level)
            print("\n[4/5] Pass 2: Detail-level filtering...")
            filtered = pass2_detail_filter(details, cache)
            print(f"  {len(filtered)} passed detail filter")
            total_pass2 += len(filtered)

            # Step 5: Transit time filter
            if args.skip_maps:
                print("\n[5/5] Skipping Maps API (--skip-maps)")
                for d in filtered:
                    from flatseeker.cache import mark_seen

                    mark_seen(
                        cache,
                        d.card.listing_id,
                        "matched_no_transit",
                        {
                            "title": d.card.title,
                            "price": d.price_chf,
                            "address": d.address,
                            "url": d.card.url,
                            "source_site": site.name,
                            "note": "Transit check skipped",
                        },
                    )
                all_matched.extend(filtered)
            else:
                print(f"\n[5/5] Pass 3: Checking transit times for {len(filtered)} listings...")
                matched = pass3_transit_filter(filtered, cache)
                all_matched.extend(matched)

        # Save cache
        save_cache(cache)

        # Generate reports
        print_console_report(all_matched, total_cards, total_pass1, total_pass2)
        generate_html_report(all_matched, total_cards)

    finally:
        close_browser(pw, browser)

    print("Done!")
    return 0 if all_matched else 1


if __name__ == "__main__":
    sys.exit(main())
