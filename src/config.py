import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Google Maps
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Filter constants
MAX_RENT_CHF = 700
MAX_TOTAL_PEOPLE = 4  # max 4 people in the flat (3 roommates + you)
MAX_TRANSIT_MINUTES = 25
TARGET_ADDRESS = "Hebelstrasse 20, 4031 Basel, Switzerland"
EARLIEST_MOVE_IN = date(2026, 6, 1)
LATEST_MOVE_IN = date(2026, 7, 31)
MAX_POST_AGE_DAYS = 30  # ignore listings older than this

# Scraping
HEADLESS = True

# Paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
CACHE_FILE = DATA_DIR / "seen_listings.json"
RESULTS_DIR = DATA_DIR / "results"
