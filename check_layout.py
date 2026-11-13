"""Screenshot AirQuality_Dashboard.html and flag layout problems.
Run: python check_layout.py   (needs: playwright install chromium)
Checks, at desktop and phone width: page-level horizontal scroll, and SVG text labels that overlap each other.
"""
import pathlib
from playwright.sync_api import sync_playwright

PAGE = pathlib.Path("AirQuality_Dashboard.html").resolve().as_uri()
SIZES = {"desktop": 1280, "phone": 390}

# Runs in the browser: returns pairs of text labels (inside one <svg>) whose boxes overlap.
FIND_OVERLAPS = """() => {
  const out = [];
  document.querySelectorAll('svg').forEach((svg, n) => {
    const t = [...svg.querySelectorAll('text')].map(e => ({s: e.textContent, r: e.getBoundingClientRect()}));
    for (let i = 0; i < t.length; i++) for (let j = i + 1; j < t.length; j++) {
      const a = t[i].r, b = t[j].r;
      const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (w > 1 && h > 1) out.push(`svg#${n}: "${t[i].s}" overlaps "${t[j].s}"`);
    }
  });
  return out;
}"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, width in SIZES.items():
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.goto(PAGE)
        scroll_w = page.evaluate("document.documentElement.scrollWidth")
        print(f"[{name} {width}px] page scrollWidth={scroll_w} -> {'OVERFLOW' if scroll_w > width else 'ok'}")
        overlaps = page.evaluate(FIND_OVERLAPS)
        print(f"[{name}] overlapping labels: {len(overlaps)}")
        for line in overlaps: print("   ", line)
        page.screenshot(path=f"dashboard_{name}.png", full_page=True)
    browser.close()
