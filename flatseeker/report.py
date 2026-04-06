import webbrowser
from datetime import date

from jinja2 import Template
from rich.console import Console
from rich.panel import Panel

from flatseeker import config
from flatseeker.config import RESULTS_DIR
from flatseeker.scraper import ListingDetail

console = Console(width=120)


def _quality_score(d: ListingDetail) -> int:
    """Score a listing 0-100 (higher = better). Used for border color."""
    score = 50
    if d.transit_min is not None:
        if d.transit_min <= 10:
            score += 25
        elif d.transit_min <= 15:
            score += 15
        elif d.transit_min <= 20:
            score += 5
        else:
            score -= 5
    if d.price_chf is not None:
        if d.price_chf <= 500:
            score += 25
        elif d.price_chf <= 600:
            score += 15
        elif d.price_chf <= 650:
            score += 5
        else:
            score -= 5
    return max(0, min(100, score))


def _quality_color(score: int) -> str:
    """Map quality score to a CSS border color."""
    if score >= 75:
        return "#4caf50"  # green
    if score >= 60:
        return "#2196F3"  # blue (default)
    if score >= 45:
        return "#ff9800"  # orange
    return "#9e9e9e"  # grey


def print_console_report(
    matched: list[ListingDetail], total_cards: int, pass1_count: int, pass2_count: int
) -> None:
    """Print a readable summary to the console."""
    console.print()
    console.print(
        Panel(
            f"[bold]Flatseeker Results - {date.today()}[/bold]\n"
            f"Total listings scraped: {total_cards}\n"
            f"After card filter (pass 1): {pass1_count}\n"
            f"After detail filter (pass 2): {pass2_count}\n"
            f"After transit filter (pass 3): {len(matched)}",
            title="Summary",
            border_style="blue",
        )
    )

    if not matched:
        console.print("\n[yellow]No new matching listings found today.[/yellow]\n")
        return

    for i, d in enumerate(matched, 1):
        price_str = f"{d.price_chf} CHF" if d.price_chf else "price unknown"
        people_str = f"{d.num_people} people" if d.num_people else "?"
        addr_str = d.address or "[yellow]no address - check manually[/yellow]"
        transit_str = f"{d.transit_min} min" if getattr(d, "transit_min", None) else "?"
        move_str = d.move_in_date or "?"
        posted_str = d.post_date or "?"

        site_str = d.card.source_site or "?"
        console.print(f"\n[bold cyan]--- Match #{i} [{site_str}] ---[/bold cyan]")
        console.print(f"  [bold]{d.card.title}[/bold]")
        console.print(f"  Price:     {price_str}")
        console.print(f"  People:    {people_str}")
        console.print(f"  Location:  {addr_str}")
        console.print(f"  Transit:   {transit_str}")
        console.print(f"  Move-in:   {move_str}")
        console.print(f"  Posted:    {posted_str}")
        console.print(f"  URL:       {d.card.url}")

    console.print()


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Flatseeker - {{ today }}</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               max-width: 1200px; margin: 0 auto; padding: 20px; background: #e8e8e8; }
        h1 { color: #333; margin-bottom: 8px; }
        .stats { background: #fff; padding: 15px; border-radius: 8px; margin-bottom: 10px;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .filters { background: #fff; padding: 12px 15px; border-radius: 8px; margin-bottom: 20px;
                   box-shadow: 0 1px 3px rgba(0,0,0,0.1); color: #666; font-size: 0.9em; }
        .filters strong { color: #333; }
        .sort-bar { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
        .sort-btn { padding: 6px 16px; border: 1px solid #ddd; border-radius: 20px;
                    background: #fff; cursor: pointer; font-size: 0.9em; color: #555;
                    transition: all 0.15s; }
        .sort-btn:hover { border-color: #2196F3; color: #2196F3; }
        .sort-btn.active { background: #2196F3; color: #fff; border-color: #2196F3; }
        .card { background: #fff; padding: 20px; border-radius: 8px; margin-bottom: 15px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #2196F3;
                transition: border-color 0.15s; }
        .card h3 { margin-top: 0; margin-bottom: 10px; }
        .card a { color: #2196F3; text-decoration: none; }
        .card a:hover { text-decoration: underline; }
        .meta { color: #666; font-size: 0.9em; }
        .tag { display: inline-block; background: #e3f2fd; color: #1565c0; padding: 2px 8px;
               border-radius: 12px; font-size: 0.85em; margin-right: 5px; margin-bottom: 4px; }
        .tag.site { background: #e0e0e0; color: #333; }
        .tag.warn { background: #fff3e0; color: #e65100; }
        .tag.good { background: #e8f5e9; color: #2e7d32; }
        .tag.unknown { background: #f5f5f5; color: #999; font-style: italic; }
        .no-results { text-align: center; color: #999; padding: 40px; }
        .description { color: #555; margin-top: 10px; margin-bottom: 0; }
    </style>
</head>
<body>
    <h1>Flatseeker Results</h1>
    <div class="stats">
        <strong>Date:</strong> {{ today }} |
        <strong>Total scraped:</strong> {{ total_cards }} |
        <strong>New matches:</strong> {{ matched | length }}
    </div>
    <div class="filters">
        <strong>Filters:</strong>
        max {{ max_rent }} CHF |
        max {{ max_people }} people |
        max {{ max_transit }} min transit |
        move-in {{ move_in_start }} to {{ move_in_end }} |
        target: {{ target_address }}
    </div>

    {% if matched %}
    <div class="sort-bar">
        <span style="line-height:32px;color:#666;font-size:0.9em;">Sort by:</span>
        <button class="sort-btn active" onclick="sortCards('quality')">Best match</button>
        <button class="sort-btn" onclick="sortCards('price')">Price</button>
        <button class="sort-btn" onclick="sortCards('transit')">Transit time</button>
        <button class="sort-btn" onclick="sortCards('date')">Newest</button>
        <button class="sort-btn" onclick="sortCards('size')">Room size</button>
    </div>

    <div id="card-container">
    {% for d in matched %}
    <div class="card" style="border-left-color: {{ d._border_color }};"
         data-price="{{ d.price_chf or 9999 }}"
         data-transit="{{ d.transit_min or 9999 }}"
         data-date="{{ d.post_date or '1970-01-01' }}"
         data-size="{{ d.size_sqm or 0 }}"
         data-quality="{{ d._quality_score }}">
        <h3><a href="{{ d.card.url }}" target="_blank">{{ d.card.title }}</a></h3>
        <div class="meta">
            {% if d.card.source_site %}<span class="tag site">{{ d.card.source_site }}</span>{% endif %}
            {% if d.price_chf %}<span class="tag good">{{ d.price_chf }} CHF</span>{% else %}<span class="tag unknown">price unknown</span>{% endif %}
            {% if d.num_people %}<span class="tag">{{ d.num_people }} people</span>{% else %}<span class="tag unknown">people unknown</span>{% endif %}
            {% if d.size_sqm %}<span class="tag">{{ d.size_sqm }} m2</span>{% endif %}
            {% if d.address %}<span class="tag">{{ d.address }}</span>{% else %}<span class="tag warn">No address - check manually</span>{% endif %}
            {% if d.move_in_date %}<span class="tag">Move-in: {{ d.move_in_date }}</span>{% endif %}
            {% if d.transit_min %}<span class="tag good">{{ d.transit_min }} min transit</span>{% else %}<span class="tag unknown">transit unknown</span>{% endif %}
            {% if d.post_date %}<span class="tag{% if d.days_since_post and d.days_since_post > 14 %} warn{% endif %}">Posted: {{ d.post_date }}{% if d.days_since_post %} ({{ d.days_since_post }}d ago){% endif %}</span>{% endif %}
        </div>
        {% if d.card.description %}<p class="description">{{ d.card.description }}</p>{% endif %}
    </div>
    {% endfor %}
    </div>

    <script>
    function sortCards(mode) {
        const container = document.getElementById('card-container');
        const cards = Array.from(container.children);
        cards.sort((a, b) => {
            if (mode === 'price') return parseFloat(a.dataset.price) - parseFloat(b.dataset.price);
            if (mode === 'transit') return parseFloat(a.dataset.transit) - parseFloat(b.dataset.transit);
            if (mode === 'date') return b.dataset.date.localeCompare(a.dataset.date);
            if (mode === 'size') return parseFloat(b.dataset.size) - parseFloat(a.dataset.size);
            if (mode === 'quality') return parseFloat(b.dataset.quality) - parseFloat(a.dataset.quality);
            return 0;
        });
        cards.forEach(c => container.appendChild(c));
        document.querySelectorAll('.sort-btn').forEach(btn => btn.classList.remove('active'));
        event.target.classList.add('active');
    }
    </script>

    {% else %}
    <div class="no-results">No new matching listings found today.</div>
    {% endif %}
</body>
</html>"""


def generate_html_report(matched: list[ListingDetail], total_cards: int) -> str:
    """Generate an HTML report and save to data/results/."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    today = date.today()
    for d in matched:
        # Compute days since post
        if d.post_date:
            try:
                pd = date.fromisoformat(d.post_date)
                d.days_since_post = (today - pd).days
            except ValueError:
                d.days_since_post = None
        else:
            d.days_since_post = None

        # Compute quality score and border color
        d._quality_score = _quality_score(d)
        d._border_color = _quality_color(d._quality_score)

    # Default sort: best quality first
    matched.sort(key=lambda d: d._quality_score, reverse=True)

    template = Template(HTML_TEMPLATE)
    html = template.render(
        today=str(today),
        total_cards=total_cards,
        matched=matched,
        max_rent=config.MAX_RENT_CHF,
        max_people=config.MAX_TOTAL_PEOPLE,
        max_transit=config.MAX_TRANSIT_MINUTES,
        move_in_start=str(config.EARLIEST_MOVE_IN),
        move_in_end=str(config.LATEST_MOVE_IN),
        target_address=config.TARGET_ADDRESS,
    )

    filename = RESULTS_DIR / f"report_{today}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    console.print(f"[green]HTML report saved to: {filename}[/green]")

    # Auto-open in browser
    webbrowser.open(str(filename))

    return str(filename)
