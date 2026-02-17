# Renderize the html to get a suitable input for the extractor (html + image(s)
from playwright.sync_api import sync_playwright

def screenshot_chart(url: str, out_path: str, selector: str = "canvas"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(url, wait_until="networkidle")

        # Wait until chart exists (canvas/svg/etc.)
        page.wait_for_selector(selector, timeout=20000)

        # If there is more than one canva, choose first one (or adjust selector)
        loc = page.locator(selector).first
        loc.scroll_into_view_if_needed()
        loc.screenshot(path=out_path)

        browser.close()


"""¿Y si no sabes el selector?

Haz primero un screenshot de la página completa para inspeccionar:

page.screenshot(path="fullpage.png", full_page=True)


Luego abres fullpage.png y decides qué selector usar (o miras el DOM con DevTools)."""

# Example usage
if __name__ == "__main__":
    screenshot_chart(
        "https://coinmarketcap.com/currencies/official-trump/",
        "chart.png",
        selector="canvas"  # prueba también "svg" si el gráfico es vectorial
    )
