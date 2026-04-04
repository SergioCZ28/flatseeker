import json
from datetime import date

from flatseeker.config import CACHE_FILE, DATA_DIR


def load_cache() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return _migrate_cache(cache)
    return {}


def _migrate_cache(cache: dict) -> dict:
    """Migrate old cache entries (no site prefix) to 'unibas:' prefix."""
    migrated = {}
    needs_migration = False
    for key, val in cache.items():
        if ":" not in key and not key.startswith("transit:"):
            migrated[f"unibas:{key}"] = val
            needs_migration = True
        else:
            migrated[key] = val
    if needs_migration:
        count = sum(1 for k in cache if ":" not in k and not k.startswith("transit:"))
        print(f"  [cache] Migrated {count} old entries to 'unibas:' prefix")
    return migrated


def save_cache(cache: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False, default=str)


def make_cache_id(site_name: str, listing_id: str) -> str:
    """Create a site-prefixed cache key."""
    return f"{site_name}:{listing_id}"


def is_seen(cache: dict, listing_id: str) -> bool:
    return listing_id in cache


def mark_seen(cache: dict, listing_id: str, status: str, details: dict) -> None:
    cache[listing_id] = {
        "first_seen": str(date.today()),
        "status": status,
        **details,
    }


def get_matched(cache: dict) -> list[dict]:
    return [{"id": k, **v} for k, v in cache.items() if v.get("status") == "matched"]
