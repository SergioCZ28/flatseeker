import os
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
CACHE_FILE = DATA_DIR / "seen_listings.json"
RESULTS_DIR = DATA_DIR / "results"
CONFIG_FILE = PROJECT_DIR / "config.yaml"

# ── Load .env (API keys) ────────────────────────────────────────────────────
load_dotenv(PROJECT_DIR / ".env")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# ── Defaults ─────────────────────────────────────────────────────────────────
DEFAULTS = {
    "target_address": "Basel SBB, 4051 Basel, Switzerland",
    "max_rent_chf": 700,
    "max_total_people": 4,
    "max_transit_minutes": 25,
    "earliest_move_in": "2026-06-01",
    "latest_move_in": "2026-07-31",
    "max_post_age_days": 30,
    "sites": ["unibas", "flatfox", "wgzimmer"],
    "flatfox_scan_window": 1500,
}


# ── Load config.yaml (fall back to defaults) ────────────────────────────────
USING_DEFAULTS = False


def _load_config() -> dict:
    global USING_DEFAULTS
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        return {**DEFAULTS, **user_config}
    USING_DEFAULTS = True
    return dict(DEFAULTS)


_cfg = _load_config()

# ── Module-level settings (used by other modules via: from flatseeker.config import X)
TARGET_ADDRESS: str = _cfg["target_address"]
MAX_RENT_CHF: int = _cfg["max_rent_chf"]
MAX_TOTAL_PEOPLE: int = _cfg["max_total_people"]
MAX_TRANSIT_MINUTES: int = _cfg["max_transit_minutes"]
MAX_POST_AGE_DAYS: int = _cfg["max_post_age_days"]
ENABLED_SITES: list[str] = _cfg["sites"]
FLATFOX_SCAN_WINDOW: int = _cfg["flatfox_scan_window"]

EARLIEST_MOVE_IN: date = date.fromisoformat(_cfg["earliest_move_in"])
LATEST_MOVE_IN: date = date.fromisoformat(_cfg["latest_move_in"])

# ── Runtime settings (can be changed by CLI flags) ───────────────────────────
HEADLESS: bool = True


# ── Interactive setup ────────────────────────────────────────────────────────


def _prompt(label: str, default: str) -> str:
    """Prompt user for a value, showing the default in brackets."""
    raw = input(f"  {label} [{default}]: ").strip()
    return raw if raw else default


def _prompt_int(label: str, default: int) -> int:
    """Prompt for a positive integer."""
    while True:
        raw = _prompt(label, str(default))
        try:
            val = int(raw)
            if val <= 0:
                raise ValueError
            return val
        except ValueError:
            print("    Please enter a positive integer.")


def _prompt_date(label: str, default: str) -> str:
    """Prompt for a date in YYYY-MM-DD format."""
    while True:
        raw = _prompt(label, default)
        try:
            date.fromisoformat(raw)
            return raw
        except ValueError:
            print("    Please enter a valid date (YYYY-MM-DD).")


def _prompt_sites(current: list[str] | None = None) -> list[str]:
    """Prompt for which sites to enable."""
    available = ["unibas", "flatfox", "wgzimmer"]
    default_sites = current if current else available
    print(f"  Available sites: {', '.join(available)}")
    raw = _prompt("Sites to scan (comma-separated)", ", ".join(default_sites))
    chosen = [s.strip().lower() for s in raw.split(",") if s.strip()]
    valid = [s for s in chosen if s in available]
    if not valid:
        print(f"    No valid sites. Using all: {', '.join(available)}")
        return available
    return valid


def init_config() -> None:
    """Interactive config setup -- creates config.yaml and .env."""
    print("\nWelcome to Flatseeker!\nLet's set up your config.\n")

    # Use existing config values as defaults if overwriting
    defaults = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        overwrite = input("  config.yaml already exists. Overwrite? [y/N]: ").strip().lower()
        if overwrite != "y":
            print("Aborted.")
            return
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
        defaults = {**defaults, **existing}

    target = _prompt("Target address (where you work/study)", defaults["target_address"])
    rent = _prompt_int("Max rent (CHF)", defaults["max_rent_chf"])
    people = _prompt_int("Max people in WG", defaults["max_total_people"])
    transit = _prompt_int("Max transit time (minutes)", defaults["max_transit_minutes"])
    age = _prompt_int("Max listing age (days)", defaults["max_post_age_days"])
    move_in_start = _prompt_date("Move-in window start (YYYY-MM-DD)", defaults["earliest_move_in"])
    move_in_end = _prompt_date("Move-in window end (YYYY-MM-DD)", defaults["latest_move_in"])
    sites = _prompt_sites(defaults.get("sites", DEFAULTS["sites"]))
    scan_window = _prompt_int("Flatfox scan window", defaults["flatfox_scan_window"])

    # Google Maps API key
    print()
    print("  Transit time filtering uses the Google Maps API.")
    print("  Get a key at: https://console.cloud.google.com/apis/credentials")
    print("  (Leave blank to skip -- you can add it later in .env)")
    api_key = input("  Google Maps API key []: ").strip()

    # Write config.yaml
    yaml_content = f"""\
# Flatseeker configuration

# Where you work/study -- transit time is calculated to this address
target_address: "{target}"

# Filter thresholds
max_rent_chf: {rent}
max_total_people: {people:<14}# max people in the WG (including you)
max_transit_minutes: {transit:<11}# public transit to target_address
max_post_age_days: {age:<12}# ignore listings older than this

# Move-in window (YYYY-MM-DD)
earliest_move_in: "{move_in_start}"
latest_move_in: "{move_in_end}"

# Sites to scan (available: unibas, flatfox, wgzimmer)
sites:
"""
    for s in sites:
        yaml_content += f"  - {s}\n"
    yaml_content += f"""
# Flatfox API scan window (number of recent listings to check)
# Lower = faster, higher = catches more if you skip days
# ~500 new listings appear per day across Switzerland
flatfox_scan_window: {scan_window}
"""

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(yaml_content)
    print(f"\n  Config saved to {CONFIG_FILE}")

    # Write .env
    if api_key:
        env_file = PROJECT_DIR / ".env"
        env_file.write_text(f"GOOGLE_MAPS_API_KEY={api_key}\n", encoding="utf-8")
        print(f"  API key saved to {env_file}")

    print("\n  Run 'flatseeker' to start scanning!")
