"""
Discovery script: opens markt.unibas.ch in a VISIBLE browser so you can inspect the DOM.

Usage:
    conda activate housing-scanner
    python discover_selectors.py

What it does:
1. Opens the housing page in a real Chrome window
2. Waits for listings to load
3. Dumps the HTML structure of the first few listing cards to console
4. Pauses so you can inspect with DevTools (F12)
5. Press Enter in the terminal to close

After running this, we'll know the exact CSS selectors to use in config.py.
"""

from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("Opening markt.unibas.ch housing page...")
        page.goto("https://markt.unibas.ch/en/search/housing")

        # Wait for content to load (the page shows "Loading posts..." initially)
        print("Waiting for listings to load...")
        page.wait_for_timeout(5000)  # 5 seconds for JS to render

        # Try to find any clickable elements that look like listing cards
        # We'll try multiple potential selectors
        potential_selectors = [
            "article",
            "[class*='card']",
            "[class*='post']",
            "[class*='listing']",
            "[class*='item']",
            "a[href*='/post/']",
            "a[href*='/housing/']",
            "[class*='Card']",
            "[class*='Post']",
        ]

        print("\n--- Searching for listing elements ---")
        for selector in potential_selectors:
            elements = page.query_selector_all(selector)
            if elements:
                print(f"\n  FOUND {len(elements)} elements matching: {selector}")
                # Show the first element's outer HTML (truncated)
                first_html = elements[0].evaluate("el => el.outerHTML")
                print(f"  First element HTML (first 500 chars):")
                print(f"  {first_html[:500]}")
                print(f"  ...")

        # Also dump the "Load more" button area
        print("\n--- Searching for pagination/load-more elements ---")
        load_more_selectors = [
            "button",
            "[class*='load']",
            "[class*='more']",
            "[class*='pagination']",
        ]
        for selector in load_more_selectors:
            elements = page.query_selector_all(selector)
            if elements:
                print(f"\n  FOUND {len(elements)} elements matching: {selector}")
                for i, el in enumerate(elements[:5]):
                    text = el.text_content().strip()[:100]
                    if text:
                        print(f"    [{i}] text: {text}")

        # Dump the full page HTML structure (just the main content area)
        print("\n--- Full page body class structure ---")
        body_html = page.evaluate("""
            () => {
                const main = document.querySelector('main') || document.body;
                // Get a simplified view of the DOM tree
                function getStructure(el, depth=0) {
                    if (depth > 4) return '';
                    const tag = el.tagName?.toLowerCase() || '';
                    const cls = el.className ? '.' + (typeof el.className === 'string' ? el.className.split(' ').join('.') : '') : '';
                    const href = el.getAttribute?.('href') || '';
                    const hrefStr = href ? ` href="${href.substring(0, 50)}"` : '';
                    let result = '  '.repeat(depth) + `<${tag}${cls}${hrefStr}>\\n`;
                    for (const child of (el.children || [])) {
                        result += getStructure(child, depth + 1);
                    }
                    return result;
                }
                return getStructure(main);
            }
        """)
        print(body_html[:3000])

        print("\n\n=== Browser is open. Inspect the page with F12 (DevTools). ===")
        print("=== Press Enter here to close the browser. ===")
        input()

        browser.close()


if __name__ == "__main__":
    main()
