from datetime import date
from rich.console import Console
from rich.panel import Panel
from jinja2 import Template
from src.config import RESULTS_DIR
from src.scraper import ListingDetail


console = Console(width=120)


def print_console_report(matched: list[ListingDetail], total_cards: int, pass1_count: int, pass2_count: int) -> None:
    """Print a readable summary to the console."""
    console.print()
    console.print(Panel(
        f"[bold]Housing Scanner Results - {date.today()}[/bold]\n"
        f"Total listings scraped: {total_cards}\n"
        f"After card filter (pass 1): {pass1_count}\n"
        f"After detail filter (pass 2): {pass2_count}\n"
        f"After transit filter (pass 3): {len(matched)}",
        title="Summary",
        border_style="blue",
    ))

    if not matched:
        console.print("\n[yellow]No new matching listings found today.[/yellow]\n")
        return

    for i, d in enumerate(matched, 1):
        price_str = f"{d.price_chf} CHF" if d.price_chf else "price unknown"
        people_str = f"{d.num_people} people" if d.num_people else "?"
        addr_str = d.address or "[yellow]no address - check manually[/yellow]"
        transit_str = f"{d.transit_min} min" if getattr(d, 'transit_min', None) else "?"
        move_str = d.move_in_date or "?"
        posted_str = d.post_date or "?"

        site_str = d.card.source_site or "?"
        console.print(f"\n[bold cyan]--- Match #{i} [{site_str}] ---[/bold cyan]")
        console.print(f"  [bold]{d.card.title}[/bold]")
        console.print(f"  Category:  {d.card.category}")
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
    <title>Housing Scanner - {{ today }}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        h1 { color: #333; }
        .stats { background: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .card { background: #fff; padding: 20px; border-radius: 8px; margin-bottom: 15px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #2196F3; }
        .card h3 { margin-top: 0; }
        .card a { color: #2196F3; }
        .meta { color: #666; font-size: 0.9em; }
        .tag { display: inline-block; background: #e3f2fd; color: #1565c0; padding: 2px 8px;
               border-radius: 12px; font-size: 0.85em; margin-right: 5px; margin-bottom: 4px; }
        .tag.warn { background: #fff3e0; color: #e65100; }
        .tag.good { background: #e8f5e9; color: #2e7d32; }
        .no-results { text-align: center; color: #999; padding: 40px; }
    </style>
</head>
<body>
    <h1>Housing Scanner Results</h1>
    <div class="stats">
        <strong>Date:</strong> {{ today }} |
        <strong>Total scraped:</strong> {{ total_cards }} |
        <strong>New matches:</strong> {{ matched | length }}
    </div>

    {% if matched %}
    {% for d in matched %}
    <div class="card">
        <h3><a href="{{ d.card.url }}" target="_blank">{{ d.card.title }}</a></h3>
        <div class="meta">
            {% if d.card.source_site %}<span class="tag" style="background:#e0e0e0;color:#333;">{{ d.card.source_site }}</span>{% endif %}
            <span class="tag">{{ d.card.category }}</span>
            {% if d.price_chf %}<span class="tag good">{{ d.price_chf }} CHF</span>{% endif %}
            {% if d.num_people %}<span class="tag">{{ d.num_people }} people</span>{% endif %}
            {% if d.address %}<span class="tag">{{ d.address }}</span>{% endif %}
            {% if d.move_in_date %}<span class="tag">Move-in: {{ d.move_in_date }}</span>{% endif %}
            {% if d.transit_min %}<span class="tag good">{{ d.transit_min }} min transit</span>{% endif %}
            {% if d.post_date %}<span class="tag{% if d.days_since_post and d.days_since_post > 14 %} warn{% endif %}">Posted: {{ d.post_date }}{% if d.days_since_post %} ({{ d.days_since_post }}d ago){% endif %}</span>{% endif %}
            {% if not d.address %}<span class="tag warn">No address - check manually</span>{% endif %}
        </div>
        <p>{{ d.card.description }}</p>
    </div>
    {% endfor %}
    {% else %}
    <div class="no-results">No new matching listings found today.</div>
    {% endif %}
</body>
</html>"""


def generate_html_report(matched: list[ListingDetail], total_cards: int) -> str:
    """Generate an HTML report and save to data/results/."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Compute days_since_post for each listing
    today = date.today()
    for d in matched:
        if d.post_date:
            try:
                pd = date.fromisoformat(d.post_date)
                d.days_since_post = (today - pd).days
            except ValueError:
                d.days_since_post = None
        else:
            d.days_since_post = None

    template = Template(HTML_TEMPLATE)
    html = template.render(
        today=str(today),
        total_cards=total_cards,
        matched=matched,
    )

    filename = RESULTS_DIR / f"report_{date.today()}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    console.print(f"[green]HTML report saved to: {filename}[/green]")
    return str(filename)
