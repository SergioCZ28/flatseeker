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
def _load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        return {**DEFAULTS, **user_config}
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
