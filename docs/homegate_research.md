# homegate.ch - Scraper Research

## Site Overview

- **What it is**: Switzerland's largest real estate marketplace (SMG Swiss Marketplace Group)
- **Tech stack**: Next.js React SPA, server-side rendered with hydration
- **Rendering**: Initial HTML has data embedded in `window.__INITIAL_STATE__` script tag as JSON
- **Public API**: None official. Internal API at `https://api.homegate.ch/search/listings` (POST)
- **Languages**: de, en, fr, it (URL path changes: mieten/rent/louer/affittare)
- **robots.txt**: Explicitly disallows most filter params (a=, ab=, ae=-an=, ao=, av=-bg=), but ALLOWS `ac=`, `ad=`, `be=`, `ep=`
- **Anti-bot measures**: **HEAVY** -- see section below

## Anti-Bot Protection (Critical)

homegate.ch uses a **dual-layer** bot protection system:

1. **DataDome** (captcha-delivery.com)
   - Slider CAPTCHA on suspicious requests
   - Blocks automated browsers (Playwright/Selenium detected immediately)
   - Also protects the API endpoint (`api.homegate.ch`)
   - Returns 403 + redirect to `geo.captcha-delivery.com/captcha/` on detection

2. **Cloudflare**
   - Challenge page with JS evaluation
   - CF Beacon fingerprinting (`cloudflareinsights.com/beacon.min.js`)
   - `cdn-cgi/challenge-platform/scripts/jsd/main.js`

3. **Detection triggers**:
   - Headless browser fingerprints
   - Missing/wrong cookies
   - Unusual request patterns
   - IP reputation (shared/datacenter IPs)
   - Plain `curl` requests always get 403
   - Even curl with full browser headers gets blocked

**Implication**: Standard requests/BeautifulSoup/Playwright will NOT work without anti-bot bypass.

## Recommended Bypass Approaches

| Approach | Complexity | Reliability | Cost |
|---|---|---|---|
| **ScrapFly with ASP** | Low | High | Paid (~$50/mo) |
| **Bright Data / residential proxies** | Medium | High | Paid |
| **Playwright + stealth + residential proxy** | High | Medium | Proxy cost |
| **RSS/Atom feed** (if exists) | Low | High | Free |
| **Manual browser session + cookie export** | Low | Fragile | Free |
| **Mobile app API reverse-engineering** | High | Medium | Free |

**Best approach for your use case**: Use Playwright with `playwright-stealth` plugin + a Swiss residential proxy, OR use the mobile app API with proper HMAC auth headers (see API section).

## Search URL Structure

### Base URL Pattern
```
https://www.homegate.ch/{lang_action}/{property_type}/{location}/matching-list?{params}
```

### Language/Action Paths
| Language | Rent | Buy |
|---|---|---|
| English | `/rent/` | `/buy/` |
| German | `/mieten/` | `/kaufen/` |
| French | `/louer/` | `/acheter/` |
| Italian | `/affittare/` | `/acquistare/` |

### Property Type Path Segments
- `real-estate` -- all property types
- `apartment` -- apartments only
- `house` -- houses/chalets/rusticos
- `commercial` -- commercial/industrial
- `dwelling` -- all residential (apartment + house)

### Location Path Segments
- `city-basel` -- specific city
- `canton-basel-stadt` -- canton
- `country-switzerland` -- country
- `region-{name}` -- region
- `zip-{code}` -- postal code
- `district-{name}` -- district within a city

### URL Query Parameters (confirmed from Google-indexed URLs)

| Parameter | Meaning | Example | Notes |
|---|---|---|---|
| `be` | Max rent price (CHF/month) | `be=700` | Gross rent |
| `an` | Min rent price (CHF/month) | `an=400` | Allowed by robots.txt only with `an=G` |
| `ac` | Min number of rooms | `ac=1` | Decimal: 1, 1.5, 2, 2.5, etc. |
| `ad` | Max number of rooms | `ad=2.5` | Decimal |
| `ep` | Page number | `ep=2` | Pagination, starts at 1 |
| `loc` | Secondary location filter | `loc=geo-city-tubach` | Additional geo filter |
| `expired` | Show expired listing | `expired=4002994974` | Listing ID |

### Target URL for Basel rooms under 700 CHF
```
https://www.homegate.ch/rent/real-estate/city-basel/matching-list?be=700
```

With room filter (e.g., 1-2.5 rooms for WG/studio):
```
https://www.homegate.ch/rent/real-estate/city-basel/matching-list?be=700&ac=1&ad=2.5
```

Page 2:
```
https://www.homegate.ch/rent/real-estate/city-basel/matching-list?be=700&ac=1&ad=2.5&ep=2
```

## Internal API (Mobile App)

### Endpoint
```
POST https://api.homegate.ch/search/listings
```

### Authentication (from homegate-rs reverse engineering)
```
Authorization: Basic REDACTED
  (REDACTED)
User-Agent: homegate.ch App Android
X-App-Id: {HMAC-calculated value}  -- changes every minute
X-App-Version: Homegate/12.6.0/12060003/Android/30
Content-Type: application/json
Accept: application/json
```

### X-App-Id Generation (Python)
```python
import hmac, hashlib, struct, math, time

SECRET = bytes([0x68, 0x6f, 0x6d, 0x65, 0x67, 0x61, 0x74, 0x65,
                0x2d, 0x61, 0x70, 0x70, 0x2d, 0x73, 0x65, 0x63,
                0x72, 0x65, 0x74, 0x2d, 0x32])
# SECRET = b"REDACTED"
USER_AGENT = "homegate.ch App Android"
APP_VERSION = "Homegate/12.6.0/12060003/Android/30"

current_minutes = math.ceil(time.time() / 60)
message = f"{USER_AGENT}{APP_VERSION}{current_minutes}"
h = hmac.new(SECRET, message.encode(), hashlib.sha256)
digest = h.digest()
app_id = struct.unpack('>i', digest[-4:])[0]
```

### Search Request Body
```json
{
  "query": {
    "offerType": "RENT",
    "location": {
      "geo": {
        "latitude": 47.5596,
        "longitude": 7.5886,
        "radius": 5000
      }
    },
    "monthlyRent": { "to": 700 },
    "numberOfRooms": { "from": 1.0, "to": 3.0 },
    "categories": ["APARTMENT", "SINGLE_ROOM", "FURNISHED_FLAT"]
  },
  "from": 0,
  "size": 20,
  "sortBy": "dateCreated",
  "sortDirection": "desc",
  "trackTotalHits": true
}
```

### Response Structure
```json
{
  "total": 42,
  "results": [
    {
      "listing": {
        "id": "4000203103",
        "address": {
          "locality": "Basel",
          "street": "...",
          "postalCode": "4051"
        },
        "categories": ["APARTMENT"],
        "characteristics": {
          "livingSpace": 45,
          "numberOfRooms": 1.5
        },
        "prices": {
          "rent": { "gross": 650 },
          "currency": "CHF"
        }
      },
      "listingType": { "type": "PREMIUM" }
    }
  ]
}
```

### API Status
**ALSO BLOCKED by DataDome** -- the API returns 403 with CAPTCHA redirect.
The app version (12.6.0) may be outdated; newer versions might use different auth.

## HTML Data Extraction (window.__INITIAL_STATE__)

When you CAN load the page (e.g., via real browser session with cookies):

### JSON Extraction
```python
import json, re

# From page HTML source
match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL)
data = json.loads(match.group(1))

# Search results
listings = data["resultList"]["search"]["fullSearch"]["result"]["listings"]
page_count = data["resultList"]["search"]["fullSearch"]["result"]["pageCount"]
```

### Listing JSON Structure (from __INITIAL_STATE__)
Each listing in the array contains:
```
listing.listing.id            -- unique listing ID
listing.listing.address       -- {locality, street, postalCode, geoCoordinates}
listing.listing.categories    -- ["APARTMENT"] etc
listing.listing.characteristics -- {livingSpace, numberOfRooms, floor}
listing.listing.prices        -- {rent: {gross, net, extra}, currency}
listing.listing.localization  -- {de: {text, title, description, urls}}
listing.listing.lister        -- {name, phone}
listing.listingType.type      -- "PREMIUM", "TOP", "STANDARD"
```

### Detail Page URL Pattern
```
https://www.homegate.ch/rent/{listing_id}
```
Example: `https://www.homegate.ch/rent/4000203103`

## HTML Selectors (from older scrapers -- may be outdated)

These class names are dynamically generated and change across deploys:
- `ListItemTopPremium_item_K9dLF` -- premium listing card
- `ListItem_item_1GcIZ` -- standard listing card

**DO NOT rely on class names** -- they are hashed/randomized. Use:
1. `window.__INITIAL_STATE__` JSON extraction (preferred)
2. Or `data-testid` attributes if they exist

## Pagination

- First page: no `ep` parameter needed
- Page N: `?ep=N` (or `&ep=N` if other params exist)
- Total pages from JSON: `data["resultList"]["search"]["fullSearch"]["result"]["pageCount"]`
- ~20 listings per page

## Property Categories (for API)

```
APARTMENT, ATTIC_FLAT, BACHELOR_FLAT, DUPLEX_APARTMENT, FURNISHED_FLAT,
GARDEN_APARTMENT, LOFT, MAISONETTE, PENTHOUSE, ROOF_FLAT, SINGLE_ROOM,
STEPPED_APARTMENT, STUDIO, TERRACE_FLAT, TRIPLEX_APARTMENT
```

For WG rooms specifically: `SINGLE_ROOM`

## Estimated Listings Count

From Google search results title: "707 Apartment for rent in Basel" (all prices).
Under 700 CHF: likely **30-80 listings** (Basel is expensive, most apartments > 1000 CHF).
WG rooms (SINGLE_ROOM) under 700: probably **10-30 listings**.

## Hack Zurich Legacy API (probably deprecated)

```
Base: https://REDACTED:443/rs/
Auth header: auth: {32-char hex key}
Endpoint: /real-estates?language=en&chooseType=rentflat&objectType=appt&zip=4001&NUMBERRESULTS=40
Detail: /real-estates/{ad_id}?language=en
```
Registration was at https://homegate.3scale.net (likely no longer active).

## Key Recommendations

1. **Scraping approach**: Use `playwright` with `playwright-stealth` plugin + Swiss residential proxy
2. **Data extraction**: Parse `window.__INITIAL_STATE__` JSON, NOT CSS selectors
3. **Rate limiting**: 2-5 second delays between pages minimum
4. **Session management**: Get initial cookies from a real browser session
5. **Alternative**: Consider if the mobile API can be made to work with updated app version/headers
6. **Fallback**: Use ScrapFly or Bright Data proxy services if DIY anti-bot bypass fails

## Sources

- [ScrapFly: How to Scrape Homegate.ch](https://scrapfly.io/blog/posts/how-to-scrape-homegate-ch-real-estate-property-data)
- [GitHub: homegate-rs (Rust unofficial API)](https://github.com/denysvitali/homegate-rs)
- [GitHub: Hack Zurich API examples](https://github.com/svenstucki/homegate-api-examples)
- [GitHub: Homegate Geneva scraper](https://github.com/bahramkhanlarov/Homegate.ch-scraping-and-data-analysis-with-Pandas)
- [Apify: Homegate Property Search Scraper](https://apify.com/ecomscrape/homegate-property-search-scraper)
