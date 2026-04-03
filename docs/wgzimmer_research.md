# wgzimmer.ch - Scraper Research

## Site Overview

- **Tech stack**: Server-rendered HTML on Apache Tomcat 9 + Magnolia CMS 6, jQuery, no SPA framework
- **Rendering**: Results are server-rendered after form POST -- no AJAX loading
- **Public API**: None. The `.rest/v1` endpoint is Magnolia admin (login-gated)
- **robots.txt**: Only disallows `/scam/` -- no scraping restrictions stated
- **Anti-bot measures**:
  - reCAPTCHA v3 (site key: `REDACTED`)
  - CSRF tokens via cookie (path-scoped to `/en/wgzimmer/search/`)
  - FuckAdBlock detection library
  - Plain curl POST returns 403 (CSRF mismatch) -- **Playwright/Selenium required**

## Search Form

**URL**: `https://www.wgzimmer.ch/en/wgzimmer/search/mate.html`
**Method**: POST (form `name="searchMateForm"`)
**Action**: `/en/wgzimmer/search/mate.html`

### Form Fields

| Field Name | Type | Values | Notes |
|---|---|---|---|
| `query` | text | free text | Search term (optional) |
| `priceMin` | select | 200-2000 (50 CHF steps) | Default: 200 |
| `priceMax` | select | 200-2000 (50 CHF steps, reverse order) | Default: 2000 |
| `wgState` | select | See region values below | Default: `all` |
| `permanent` | radio | `all`, `true`, `false` | all=both, true=unlimited only, false=temporary only |
| `student` | radio | `none`, `true`, `false` | none=all, true=students only, false=no students |
| `studio` | checkbox | `true` | Only ateliers/studios |
| `typeofwg` | radio | `all`, `senior` | Default: all |
| `startSearch` | hidden | `true` | Always true |
| `bypass-csrf` | hidden | `true` | Always true |
| `g-recaptcha-response` | hidden | token string | Populated by reCAPTCHA v3 JS |

### Basel Region Values

| Display Name | `wgState` value |
|---|---|
| Search All | `all` |
| Basel (Stadt) | `baselstadt` |
| Basel (Land) | `baselland` |

### Target Search Parameters

For Basel WG rooms under 700 CHF:
```
wgState=baselstadt
priceMin=200
priceMax=700
permanent=all
student=none
typeofwg=all
```

## Search Results Page Structure

### Listing Card HTML

```html
<li class="search-result-entry search-mate-entry">
  <div class="wishlistResultlist wishlistStar">...</div>
  <script>...</script>
  <a href="/wglink/de/{uuid}/{state}/{date}-{id}-{state}.html">
    <div class="create-date left-image-result">
      <strong>{post_date}</strong>  <!-- e.g. "March 25, 2026" -->
    </div>
    <span class="thumb">
      <img id="resultlist-image-preview-{n}" src="https://img.wgzimmer.ch/.imaging/wgzimmer_resultlist-jpg/dam/{uuid}/temp.jpg">
    </span>
    <span class="state image">
      <span class="thumbState">
        <strong>{region}</strong>     <!-- e.g. "Basel (city)" -->
        <font>{neighborhood}</font>  <!-- e.g. "Am Ring" -->
        <br>
        <font>{nearby}</font>         <!-- e.g. "University, Art Museum, Old Town" -->
      </span>
    </span>
    <span class="from-date">
      <strong>{available_from}</strong>  <!-- e.g. "May 1, 2026" -->
      <font>{until_text}</font>          <!-- e.g. "Until: Indefinitely" or "Until: June 30, 2026" -->
    </span>
    <span class="cost">
      <strong>{price}</strong>           <!-- e.g. "480" (number only, no currency) -->
    </span>
  </a>
</li>
```

### CSS Selectors for Listing Extraction

| Data | Selector | Notes |
|---|---|---|
| All listings | `li.search-result-entry.search-mate-entry` | Excludes ad entries |
| Detail link | `li.search-mate-entry a` | `href` attribute = detail URL |
| Post date | `.create-date strong` | |
| Region | `.state .thumbState strong` | e.g. "Basel (city)" |
| Neighborhood | `.state .thumbState font:first-of-type` | e.g. "Am Ring" |
| Nearby | `.state .thumbState font:last-of-type` | e.g. "University, Art Museum" |
| Available from | `.from-date strong` | |
| Available until | `.from-date font` | |
| Price (CHF) | `.cost strong` | Number only |
| Thumbnail | `.thumb img` | `src` attribute |

### Listing URL Pattern

```
/wglink/{lang}/{uuid}/{state}/{date}-{id}-{state}.html
```
Example: `/wglink/de/f0287078-6d49-4f90-bbb9-e6d0dc4adae4/baselstadt/1-5-2026-512-baselstadt.html`

### Pagination

- Results page header shows: "Total {N} listings" and "Page {X}/{Y}"
- Navigation uses `.result-navigation` div
- **Cursor-based**, not offset-based: next page link is `?id={uuid}` where the UUID is the last listing on the current page
- ~24 real listings per page (excluding ~5 ad items interspersed)
- Ads are `li.search-result-entry` WITHOUT the `search-mate-entry` class

### Result Sorting

The header row shows sortable columns: "AUFGEGEBEN" (posted), "REGION", "AB DEM" (from), "MIETE/MONAT" (rent/month). Default sort appears to be by post date descending.

## Detail Page Structure

**URL**: Same as listing link (absolute: `https://www.wgzimmer.ch/wglink/de/{uuid}/...`)
**Access**: Direct GET request works -- no reCAPTCHA needed for detail pages.

### Sections

```
div.date-cost
  h3.label  "Daten und Miete"
  p > strong "Ab dem"       + text "1.5.2026"
  p > strong "Bis"          + text "Unbefristet" | date
  p > strong "Miete / Monat" + text "sFr. 480 .--"

div.adress-region
  h3.label  "Adresse"
  p > strong "Region"           + text "Basel (Stadt)"
  p > strong "Adresse"          + text "Rosshofgasse 20"
  p > strong "Ort"              + text "4051 Basel"
  p > strong "Kreis / Quartier" + text "Am Ring"
  p > strong "In der Naehe"     + text "Universitaet, Kunstmuseum, Altstadt"

div.person-content     "Wir sind"    -- flatmate description
div.room-content       "Wir suchen"  -- what they're looking for
div.mate-content       "Das Zimmer ist" -- room description
div.image-content      -- up to 3 images (loaded via JS: xhrRenderImage)
div.mate-contact       -- contact info (hidden behind JS click)
```

### CSS Selectors for Detail Extraction

| Data | Selector | Parsing |
|---|---|---|
| Available from | `.date-cost p:nth-child(2)` | Text after `<strong>` |
| Available until | `.date-cost p:nth-child(3)` | Text after `<strong>` |
| Rent | `.date-cost p:nth-child(4)` | Text after `<strong>`, parse number |
| Region | `.adress-region p:nth-child(2)` | Text after `<strong>` |
| Address | `.adress-region p:nth-child(3)` | Text after `<strong>` |
| City/ZIP | `.adress-region p:nth-child(4)` | Text after `<strong>` |
| Quarter | `.adress-region p:nth-child(5)` | Text after `<strong>` |
| Nearby | `.adress-region p:nth-child(6)` | Text after `<strong>` |
| Room description | `.mate-content` | Full text content |
| Flatmates | `.person-content` | Full text content |
| Requirements | `.room-content` | Full text content |
| Images | `.image-content a[href]` | Images lazy-loaded via JS |

## Scraper Strategy

### Recommended Approach: Playwright

Since reCAPTCHA v3 is mandatory for search results, use Playwright with a real Chromium browser:

1. **Navigate** to `https://www.wgzimmer.ch/en/wgzimmer/search/mate.html`
2. **Accept cookies** (dismiss consent dialog)
3. **Set form values**: wgState=baselstadt, priceMax=700
4. **Click SEARCH** -- reCAPTCHA v3 runs automatically (score-based, no user interaction)
5. **Wait for results** to load (selector: `li.search-mate-entry`)
6. **Parse listings** from the search results page
7. **Detail pages can be fetched via plain HTTP** (no reCAPTCHA) for additional info
8. **Pagination**: click "Next" or follow `?id={uuid}` links if needed

### Why Not Plain HTTP

- POST requires valid `g-recaptcha-response` token
- CSRF token in cookie must match session
- Without reCAPTCHA token: either 403 or form page returned without results
- The reCAPTCHA v3 token requires browser JavaScript execution

### Detail Pages Are Free

Detail pages (`/wglink/...`) load via plain GET with no reCAPTCHA. Once you have listing URLs from the search results page, you can fetch details with `requests`/`httpx` directly -- no browser needed.

### Image Loading

Images on detail pages are lazy-loaded via JavaScript (`xhrRenderImage()`). The image URL pattern is:
```
https://img.wgzimmer.ch/.imaging/wgzimmer_medium/dam/{uuid}/temp.jpg
```
For thumbnails (search results):
```
https://img.wgzimmer.ch/.imaging/wgzimmer_resultlist-jpg/dam/{uuid}/temp.jpg
```

## Existing Open-Source Scrapers

- [maroth/wgzimmer](https://github.com/maroth/wgzimmer) -- Python CLI, uses POST without reCAPTCHA (likely broken now)
- [bskdany/WokoWGZScraperBot](https://github.com/bskdany/WokoWGZScraperBot) -- Python Telegram bot, same approach (likely broken)

Both predate the reCAPTCHA v3 addition and use plain `requests.post()`.
