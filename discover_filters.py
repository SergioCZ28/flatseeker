"""Quick script to discover how the site filters work -- what selectors to click."""

from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto("https://markt.unibas.ch/en/search/housing")
        page.wait_for_timeout(5000)

        # Find all select/dropdown elements
        print("=== SELECT elements ===")
        selects = page.query_selector_all("select")
        for i, s in enumerate(selects):
            name = s.get_attribute("name") or s.get_attribute("id") or ""
            print(f"  [{i}] name={name}")
            options = s.query_selector_all("option")
            for opt in options[:10]:
                val = opt.get_attribute("value") or ""
                txt = opt.inner_text().strip()
                print(f"       value='{val}' text='{txt}'")

        # Find mantine Select components (the site uses Mantine UI)
        print("\n=== Mantine Select / Input elements ===")
        inputs = page.query_selector_all("input[role='searchbox'], input[class*='Select'], [class*='mantine-Select']")
        for i, inp in enumerate(inputs):
            placeholder = inp.get_attribute("placeholder") or ""
            aria = inp.get_attribute("aria-label") or ""
            cls = inp.get_attribute("class") or ""
            print(f"  [{i}] placeholder='{placeholder}' aria='{aria}' class_short='{cls[:80]}'")

        # Find all buttons/inputs in the filter area
        print("\n=== Filter area elements ===")
        filter_area = page.query_selector("div.grid.grid-cols-1.gap-4")
        if filter_area:
            children = filter_area.query_selector_all("button, input, select, [role='combobox']")
            for i, ch in enumerate(children):
                tag = ch.evaluate("el => el.tagName")
                text = ch.inner_text().strip()[:50] if ch.inner_text() else ""
                placeholder = ch.get_attribute("placeholder") or ""
                role = ch.get_attribute("role") or ""
                print(f"  [{i}] <{tag}> text='{text}' placeholder='{placeholder}' role='{role}'")

        # Check if URL params work for filtering
        print("\n=== Testing URL-based filters ===")
        # Try adding query params
        test_urls = [
            "https://markt.unibas.ch/en/search/housing?type=offers",
            "https://markt.unibas.ch/en/search/housing?subcategory=shared-room",
        ]
        for url in test_urls:
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(3000)
            cards = page.query_selector_all("a[href*='/post/']")
            h1 = page.query_selector("h1")
            h1_text = h1.inner_text() if h1 else ""
            print(f"  {url}")
            print(f"    -> {len(cards)} cards, h1='{h1_text}'")

        print("\n=== Browser open. Press Enter to close. ===")
        input()
        browser.close()


if __name__ == "__main__":
    main()
