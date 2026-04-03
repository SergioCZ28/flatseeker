import json

d = json.load(open("data/seen_listings.json"))

# Filter out transit cache entries
listings = {k: v for k, v in d.items() if isinstance(v, dict) and "status" in v}

# Count by status
from collections import Counter
statuses = Counter(v["status"] for v in listings.values())
print("=== Filter breakdown ===")
for s, c in statuses.most_common():
    print(f"  {s:30s} {c}")

print()

# Show matched
matches = [v for v in listings.values() if v["status"].startswith("matched")]
print(f"=== {len(matches)} Matched listings ===\n")
for i, v in enumerate(sorted(matches, key=lambda x: x.get("price") or 9999), 1):
    price = v.get("price", "?")
    transit = v.get("transit_min", "?")
    post = v.get("post_date", "?")
    title = v["title"][:60]
    addr = v.get("address", "no addr")
    if addr and len(addr) > 25:
        addr = addr[:25]
    print(f"{i:2}. {str(price):>4} CHF | {str(transit):>3} min | {str(post):>10} | {addr:25s} | {title}")
