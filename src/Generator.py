import base64
import json
from pathlib import Path
from groq import Groq

client = Groq()

def encode_image(image_path: str) -> str:
    """Converts image to base64 string for the API."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def generate_alt_text_groq(
    image_path_1: str,
    image_path_2: str,
    html_context: str = "",
) -> str:
    """
    Generates alt text using Llama 4 Scout via Groq.
    Accepts two chart images + optional HTML context snippet.
    """
    img1_b64 = encode_image(image_path_1)
    img2_b64 = encode_image(image_path_2)

    # Truncate HTML to avoid hitting token limits
    html_snippet = html_context[:1500] if html_context else "Not provided."

    completion = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img1_b64}"},
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img2_b64}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "You are an accessibility expert writing alt text for data visualizations.\n"
                            "The two images show the same chart: the first is a full-page view, "
                            "the second is a close-up of the chart itself.\n\n"
                            f"HTML context surrounding the chart:\n```html\n{html_snippet}\n```\n\n"
                            "Write a concise alt text (2-3 sentences). "
                            "Include: chart type, what is being measured, and the key takeaway. "
                            "Do not describe colors or visual style. "
                            "Output only the alt text, nothing else."
                            "Then, add a meaningful and short take away from the visualization regarding the data on it (analyze trends, important conclusion )"
                        ),
                    },
                ],
            }
        ],
        temperature=0.2,        # low temp for factual, consistent output
        max_completion_tokens=150,
        top_p=1,
        stream=False,           # simpler to handle for a single alt text string
        stop=None,
    )

    return completion.choices[0].message.content.strip()

def enrich_results_with_alt_text(results_json_path: str, use_groq: bool = True):
    with open(results_json_path, encoding="utf-8") as f:
        results = json.load(f)

    for entry in results:
        charts = entry.get("charts", [])
        img_paths = [c["image_path"] for c in charts if c.get("image_path")]
        if not img_paths:
            continue

        img1 = img_paths[0]
        img2 = img_paths[1] if len(img_paths) > 1 else img_paths[0]

        html_snippet = ""
        if entry.get("html_path") and Path(entry["html_path"]).exists():
            html_snippet = Path(entry["html_path"]).read_text(encoding="utf-8")

        for chart in charts:
            if chart.get("has_alt"):
                print(f"  Skipping chart {chart['rank']} — already has alt text")
                continue

            print(f"  Generating alt for chart {chart['rank']}...")

            # Switch between models here
            if use_groq:
                alt = generate_alt_text_groq(img1, img2, html_snippet)
                source = "llama4-scout-groq"
            else:
                alt = generate_alt_text(img1, img2, html_snippet)  # Qwen2-VL
                source = "qwen2vl"

            chart["alt_text"] = alt
            chart["has_alt"] = True
            chart["alt_source"] = source

        entry["has_alt"] = any(c["has_alt"] for c in charts)

    with open(results_json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)