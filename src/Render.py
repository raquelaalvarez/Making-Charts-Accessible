# Renderize the html to get a suitable input for the extractor (html + image(s)
from playwright.sync_api import sync_playwright


"""def screenshot_chart(url: str, out_path: str, selector: str = "canvas, svg"):
    # es podria fer un bucle que provi diferents formats de selector fins que trobi un que funcioni ( i no doni timeout error))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        
        page.goto(url, wait_until= "domcontentloaded")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)  
        page.wait_for_selector(selector, state="visible", timeout=60000)

        element = page.locator(selector).first
        
        element.scroll_into_view_if_needed()
        element.screenshot(path=out_path, animations="disabled")

        browser.close()"""

def screenshot_chart(url: str, out_path: str):
    # "Chart detection based on visual prominence heuristics (largest SVG element in DOM)."
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(3000)

        svgs = page.locator("svg")
        count = svgs.count()

        if count == 0:
            raise RuntimeError("No SVGs found")
        # print(count)
        largest = None
        largest_area = 0

        for i in range(count):
            el = svgs.nth(i)
            box = el.bounding_box()
            if box:
                area = box["width"] * box["height"]
                if area > largest_area:
                    largest_area = area
                    largest = el

        if largest is None:
            raise RuntimeError("No visible SVG found")

        largest.scroll_into_view_if_needed()
        largest.screenshot(path=out_path)

        browser.close()

def debug_page(url: str):
    # y si nos quedasemos solo con la captura de la página web?
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)  # deja respirar el JS

        page.screenshot(path="fullpage.png", full_page=True)
        html = page.content()
        with open("page.html", "w", encoding="utf-8") as f:
            f.write(html)

        browser.close()



"""¿Y si no sabes el selector?

Haz primero un screenshot de la página completa para inspeccionar:

page.screenshot(path="fullpage.png", full_page=True)


Luego abres fullpage.png y decides qué selector usar (o miras el DOM con DevTools)."""

"""Te recomiendo guardar también:

html = page.content()
with open("page.html", "w", encoding="utf-8") as f:
    f.write(html)"""

# Example usage
if __name__ == "__main__":
    debug_page("https://hackupc.com/") # checks the page and creates fullpage.png to see what the web page is looking like.


    screenshot_chart(
        "https://hackupc.com/",
        "chart.png",
    
    )
