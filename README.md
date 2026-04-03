# Flatseeker

Automated WG room scanner for Basel, Switzerland. Scrapes listings from multiple housing sites, filters by price, transit time, move-in date, and more, then generates a daily HTML report of matches.

## Sites

| Site | Type | Method |
|------|------|--------|
| [markt.unibas.ch](https://markt.unibas.ch) | University bulletin board | Browser (Playwright) |
| [flatfox.ch](https://flatfox.ch) | Rental platform | JSON API |
| [wgzimmer.ch](https://wgzimmer.ch) | WG room marketplace | Browser (Playwright) |

## How it works

```
Scrape cards  -->  Filter (card text)  -->  Scrape details  -->  Filter (full text)  -->  Transit time check
   fast               free                    slow                  free                   Google Maps API
```

Listings are cached so they're only processed once. Each run only looks at new listings.

## Setup

1. Clone and install:
   ```bash
   git clone https://github.com/SergioCZ28/flatseeker.git
   cd flatseeker
   pip install -e .
   playwright install chromium
   ```

2. Configure:
   ```bash
   cp config.example.yaml config.yaml   # edit with your preferences
   cp .env.example .env                 # add your Google Maps API key
   ```

3. Run:
   ```bash
   flatseeker
   ```

## CLI flags

| Flag | Description |
|------|-------------|
| `--no-headless` | Show browser window (for debugging) |
| `--skip-maps` | Skip Google Maps API calls |
| `--force-refresh` | Ignore cache, reprocess all listings |
| `--limit N` | Only process first N new listings (for testing) |
| `--sites unibas,flatfox` | Only scan specific sites |
| `--check-results` | Show cache breakdown and matched listings |

## Configuration

Edit `config.yaml` to set your preferences:

```yaml
target_address: "Basel SBB, 4051 Basel, Switzerland"
max_rent_chf: 700
max_transit_minutes: 25
earliest_move_in: "2026-06-01"
latest_move_in: "2026-07-31"
sites: [unibas, flatfox, wgzimmer]
```

The Google Maps API key goes in `.env` (never committed to git).

## Adding a new site

Create a new file in `flatseeker/sites/` that inherits from `BaseSite` and implements:
- `scrape_cards(page)` -- return a list of `ListingCard`
- `scrape_detail(page, card)` -- return a `ListingDetail`

Register it in `flatseeker/sites/__init__.py` and add it to `config.yaml`.

## Requirements

- Python 3.11+
- Google Maps API key (Directions API enabled) for transit time filtering
