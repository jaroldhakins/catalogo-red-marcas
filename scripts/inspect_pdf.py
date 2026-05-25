import json
import sys

import fitz


pdf = "Catalogo completo Red de Marcas-1.pdf"
page_number = int(sys.argv[1]) if len(sys.argv) > 1 else 2
doc = fitz.open(pdf)
page = doc[page_number - 1]
items = []

for block in page.get_text("dict")["blocks"]:
    bbox = [round(value, 1) for value in block["bbox"]]
    if block["type"] == 0:
        text = "\n".join(
            "".join(span["text"] for span in line["spans"])
            for line in block["lines"]
        ).strip()
        items.append({"type": "text", "bbox": bbox, "text": text})
    elif block["type"] == 1:
        items.append({
            "type": "image",
            "bbox": bbox,
            "w": block.get("width"),
            "h": block.get("height"),
        })

items.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))
print(json.dumps(items, ensure_ascii=False, indent=2))
