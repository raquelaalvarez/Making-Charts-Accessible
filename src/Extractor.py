"""
render_pipeline.py
------------------
Lee URLs de un CSV de entrada, renderiza cada página con Playwright y guarda:
  - HTML completo de la página
  - Capturas de TODOS los SVGs/charts grandes (o fullpage si no hay SVG)
  - ALT text de cada elemento (si existe)
  - Metadatos en un JSON de salida

Estructura de salida:
  output_dir/
    results.json
    images/
      <slug>_chart_1.png
      <slug>_chart_2.png
      ...
      <slug>_fullpage.png   (si no hay SVGs)
    html/
      <slug>.html

Uso:
  python render_pipeline.py --input urls.csv --output output_dir

El CSV de entrada debe tener al menos una columna 'url'.
"""

import argparse
import csv
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(url: str) -> str:
    """Convierte una URL en un nombre de archivo seguro."""
    slug = re.sub(r"https?://", "", url)
    slug = re.sub(r"[^\w\-]", "_", slug)
    return slug[:80]  # limita longitud


def extract_alt_from_svg(page, svg_locator) -> str:
    """
    Intenta obtener un texto ALT del SVG:
      1. Atributo aria-label del SVG
      2. <title> hijo del SVG
      3. <desc> hijo del SVG
      4. Atributo alt (poco común pero posible)
    Devuelve cadena vacía si no encuentra nada.
    """
    try:
        aria = svg_locator.get_attribute("aria-label") or ""
        if aria.strip():
            return aria.strip()

        title = svg_locator.locator("title").first
        if title.count() > 0:
            t = title.inner_text()
            if t.strip():
                return t.strip()

        desc = svg_locator.locator("desc").first
        if desc.count() > 0:
            d = desc.inner_text()
            if d.strip():
                return d.strip()

        alt = svg_locator.get_attribute("alt") or ""
        return alt.strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Core render logic
# ---------------------------------------------------------------------------

def extract_info_from_url(
    url: str,
    images_dir: Path,
    html_dir: Path,
    min_svg_area: float = 5_000,
) -> dict:
    """
    Procesa una URL y devuelve un dict con los resultados.

    Args:
        min_svg_area: área mínima en px² para considerar un SVG como relevante.
                      SVGs más pequeños (iconos, decorativos) se ignoran.
    """
    result = {
        "url": url,
        "status": "ok",
        "error": "",
        "has_svg": False,
        "svg_count": 0,
        "charts": [],          # lista de {rank, area, alt_text, has_alt, image_path}
        "image_paths": [],     # acceso rápido a todas las rutas de imagen
        "html_path": "",
    }

    slug = slugify(url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        try:
            page.goto(url, wait_until="networkidle", timeout=30_000)
        except Exception:
            # Fallback: domcontentloaded es más permisivo
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            except Exception as e:
                result["status"] = "error"
                result["error"] = f"goto failed: {e}"
                browser.close()
                return result

        page.wait_for_timeout(3000)

        # --- Guardar HTML ---
        html_path = html_dir / f"{slug}.html"
        try:
            html = page.content()
            html_path.write_text(html, encoding="utf-8")
            result["html_path"] = str(html_path)
        except Exception as e:
            result["error"] += f" | html error: {e}"

        # --- Detectar SVGs ---
        svgs = page.locator("svg")
        count = svgs.count()

        if count > 0:
            result["has_svg"] = True

            # Recoger todos los SVGs con su área de bounding box
            svg_candidates = []
            for i in range(count):
                el = svgs.nth(i)
                box = el.bounding_box()
                if box:
                    area = box["width"] * box["height"]
                    if area >= min_svg_area:
                        svg_candidates.append((area, i, el))

            # Ordenar de mayor a menor área
            svg_candidates.sort(key=lambda x: x[0], reverse=True)
            result["svg_count"] = len(svg_candidates)

            if svg_candidates:
                for rank, (area, _idx, el) in enumerate(svg_candidates, start=1):
                    chart_info = {
                        "rank": rank,
                        "area_px2": round(area),
                        "alt_text": "",
                        "has_alt": False,
                        "image_path": "",
                    }

                    # ALT text
                    alt = extract_alt_from_svg(page, el)
                    chart_info["alt_text"] = alt
                    chart_info["has_alt"] = bool(alt)

                    # Screenshot del SVG
                    img_path = images_dir / f"{slug}_chart_{rank}.png"
                    try:
                        el.scroll_into_view_if_needed()
                        el.screenshot(path=str(img_path))
                        chart_info["image_path"] = str(img_path)
                        result["image_paths"].append(str(img_path))
                    except Exception as e:
                        result["error"] += f" | svg_{rank} screenshot error: {e}"
                        # Fallback: screenshot de página completa para este SVG
                        img_path = images_dir / f"{slug}_chart_{rank}_fullpage.png"
                        try:
                            page.screenshot(path=str(img_path), full_page=True)
                            chart_info["image_path"] = str(img_path)
                            result["image_paths"].append(str(img_path))
                        except Exception as e2:
                            result["error"] += f" | fallback screenshot error: {e2}"

                    result["charts"].append(chart_info)

            else:
                # SVGs existen pero todos son demasiado pequeños (iconos, etc.)
                result["has_svg"] = False
                img_path = images_dir / f"{slug}_fullpage.png"
                page.screenshot(path=str(img_path), full_page=True)
                result["image_paths"].append(str(img_path))

        else:
            # Sin SVG: screenshot completo de la página
            img_path = images_dir / f"{slug}_fullpage.png"
            try:
                page.screenshot(path=str(img_path), full_page=True)
                result["image_paths"].append(str(img_path))
            except Exception as e:
                result["error"] += f" | fullpage screenshot error: {e}"

        browser.close()

    return result


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def run_pipeline(
    input_csv: str,
    output_dir: str,
    url_column: str = "url",
    min_svg_area: float = 5_000,
):
    output_path = Path(output_dir)
    images_dir = output_path / "images"
    html_dir = output_path / "html"

    output_path.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(exist_ok=True)
    html_dir.mkdir(exist_ok=True)

    # Leer URLs del CSV de entrada
    with open(input_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("El CSV de entrada está vacío.")
        return

    if url_column not in rows[0]:
        url_column = list(rows[0].keys())[0]
        print(f"Columna 'url' no encontrada, usando '{url_column}'")

    results_path = output_path / "results.json"

    # Cargar resultados previos si existen (permite reanudar ejecuciones interrumpidas)
    if results_path.exists():
        with open(results_path, encoding="utf-8") as f:
            all_results = json.load(f)
        processed_urls = {r["url"] for r in all_results}
        print(f"Retomando: {len(processed_urls)} URLs ya procesadas.")
    else:
        all_results = []
        processed_urls = set()

    total = len(rows)
    for idx, row in enumerate(rows, 1):
        url = row[url_column].strip()
        if not url:
            continue

        if url in processed_urls:
            print(f"[{idx}/{total}] Saltando (ya procesada): {url}")
            continue

        print(f"[{idx}/{total}] Procesando: {url}")
        t0 = time.time()

        try:
            result = extract_info_from_url(url, images_dir, html_dir, min_svg_area)
        except Exception as e:
            result = {
                "url": url, "status": "error", "error": str(e),
                "has_svg": False, "svg_count": 0,
                "charts": [], "image_paths": [], "html_path": "",
            }

        result["elapsed_seconds"] = round(time.time() - t0, 2)

        # Resumen de ALTs para el log
        alts_found = sum(1 for c in result.get("charts", []) if c["has_alt"])
        print(
            f"  {'✓' if result['status'] == 'ok' else '✗'} "
            f"{result['elapsed_seconds']}s | "
            f"has_svg={result['has_svg']} | "
            f"svg_count={result['svg_count']} | "
            f"alts={alts_found}/{result['svg_count']}"
        )

        all_results.append(result)

        # Guardar tras cada URL para no perder progreso si algo falla
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\nCompletado. {len(all_results)} entradas guardadas en '{results_path}'")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    BASE_DIR = Path(__file__).parent

    input_csv = BASE_DIR / "DataBase" / "Links_webs_BD.csv"
    output_dir = BASE_DIR / "DataBase"
    url_column = "URLS"
    min_svg_area = 5_000   # px² — ajusta para filtrar iconos pequeños

    run_pipeline(input_csv, output_dir, url_column, min_svg_area)