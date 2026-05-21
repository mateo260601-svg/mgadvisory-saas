from pathlib import Path
import json
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pptx import Presentation


TEMPLATE_DIR = Path("templates") / "pptx"
OUTPUT = TEMPLATE_DIR / "template_manifest.json"


def extract_text(slide) -> str:
    parts = []
    for shape in slide.shapes:
        if hasattr(shape, "text") and shape.text:
            clean = " ".join(shape.text.split())
            if clean:
                parts.append(clean)
    return " | ".join(parts)[:500]


manifest = {
    "templates": [],
    "usage_principles": [
        "Use book_schemas_janvier_2023_reference.pptx as the slide-pattern library for charts, process pages, tables and analytics layouts.",
        "Use jbf_ge_im_draft_reference.pptx as the IM / M&A narrative reference for executive flow, section rhythm and buyer-facing story.",
        "Generated decks should inherit the analytical grammar and density, not blindly clone client-confidential wording.",
    ],
}

for path in sorted(TEMPLATE_DIR.glob("*_reference.pptx")):
    prs = Presentation(str(path))
    slides = []
    for idx, slide in enumerate(prs.slides, start=1):
        text = extract_text(slide)
        slides.append(
            {
                "slide": idx,
                "layout": slide.slide_layout.name,
                "text_preview": text,
                "shape_count": len(slide.shapes),
            }
        )
    manifest["templates"].append(
        {
            "file": path.name,
            "slide_count": len(prs.slides),
            "slide_width": prs.slide_width,
            "slide_height": prs.slide_height,
            "slides": slides,
        }
    )

OUTPUT.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps({"templates": len(manifest["templates"]), "output": str(OUTPUT)}, indent=2))
