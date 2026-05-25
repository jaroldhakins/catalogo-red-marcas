import argparse
import csv
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import fitz


PDF = Path("Catalogo completo Red de Marcas-1.pdf")
OUT_DIR = Path("data/extraccion-catalogo")
PUBLIC_PRODUCTS = Path("public/productos")
DB = Path("data/catalogo.sqlite")

CODE_RE = re.compile(r"^\d{6,8}$")
PRICE_RE = re.compile(r"^\$?[\d.,]+$")

AUDIT_FIELDS = [
    "orden",
    "pagina",
    "codigo",
    "nombre",
    "marca",
    "categoria",
    "imagen",
    "estado",
]


@dataclass
class ImageItem:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def area(self) -> float:
        return self.width * self.height

    def clip(self, page_rect: fitz.Rect, padding: float = 8) -> fitz.Rect:
        return fitz.Rect(
            max(0, self.x0 - padding),
            max(0, self.y0 - padding),
            min(page_rect.width, self.x1 + padding),
            min(page_rect.height, self.y1 + padding),
        )


def clean(value: str) -> str:
    return " ".join(value.replace("\n", " ").split()).strip()


def words_for_page(page: fitz.Page) -> list[dict]:
    words = []
    for raw in page.get_text("words"):
        x0, y0, x1, y1, text, block, line, word = raw[:8]
        words.append({
            "x0": x0,
            "y0": y0,
            "x1": x1,
            "y1": y1,
            "cx": (x0 + x1) / 2,
            "cy": (y0 + y1) / 2,
            "text": text.strip(),
            "block": block,
            "line": line,
            "word": word,
        })
    return words


def product_images(page: fitz.Page, page_index: int) -> list[ImageItem]:
    images = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 1:
            continue
        item = ImageItem(page_index, *block["bbox"])
        if item.width < 22 or item.height < 22:
            continue
        if item.area > 45_000:
            continue
        if item.width > 130 and item.height > 250:
            continue
        if item.x0 < 2 and item.height > 500:
            continue
        images.append(item)
    return images


def row_key(image: ImageItem) -> tuple[int, float]:
    return (round(image.cy / 55), image.x0)


def visual_order(images: list[ImageItem]) -> list[ImageItem]:
    return sorted(images, key=row_key)


def code_for_image(image: ImageItem, words: list[dict]) -> dict | None:
    candidates = []
    for word in words:
        if not CODE_RE.match(word["text"]):
            continue
        horizontal = abs(word["cx"] - image.cx)
        below = word["cy"] - image.y1
        inside_or_below = word["cy"] - image.cy
        if horizontal > max(85, image.width * 0.8):
            continue
        if below < -18 or below > 95:
            continue
        score = horizontal * 1.2 + abs(below - 28)
        candidates.append((score, word))

        if -5 <= below <= 65:
            candidates.append((score * 0.8, word))

    if not candidates:
        # Some compact cells place the code just under a small text block.
        for word in words:
            if not CODE_RE.match(word["text"]):
                continue
            horizontal = abs(word["cx"] - image.cx)
            vertical = word["cy"] - image.cy
            if horizontal <= max(90, image.width) and 10 <= vertical <= 170:
                candidates.append((horizontal * 1.3 + abs(vertical - 95), word))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def text_between(image: ImageItem, code: dict, words: list[dict]) -> list[str]:
    left = min(image.x0, code["x0"]) - 35
    right = max(image.x1, code["x1"]) + 35
    top = image.y1 - 12
    bottom = code["y0"] + 4
    selected = [
        word for word in words
        if left <= word["cx"] <= right
        and top <= word["cy"] <= bottom
        and word["text"] != code["text"]
        and not PRICE_RE.match(word["text"])
    ]
    selected.sort(key=lambda item: (item["y0"], item["x0"]))
    return [word["text"] for word in selected]


def normalize_name(tokens: list[str], code: str) -> str:
    ignored = {"red", "de", "marcas"}
    clean_tokens = []
    for token in tokens:
        value = token.strip(" ,;")
        if not value:
            continue
        if value == code or CODE_RE.match(value) or PRICE_RE.match(value):
            continue
        if value.lower() in ignored:
            continue
        clean_tokens.append(value)

    name = clean(" ".join(clean_tokens))
    name = name.replace("Blabca", "Blanca")
    name = re.sub(r"\bGlina\.\s+Glina\.\s+", "Glina. ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or f"Producto {code}"


BRAND_RULES = [
    ("Sello Rojo", ["SELLO ROJO", "SELLO RO"]),
    ("Bastilla", ["BASTILLA", "BASTIYÁ", "BASTIYA"]),
    ("Matiz", ["MATIZ"]),
    ("Colcafe", ["COLCAFE", "COLCAFÉ", "CAPPUCCINO"]),
    ("Jet", [" JET ", "GLINA. JET", "ALBUM JET", "ÁLBUM JET"]),
    ("Jumbo", ["JUMBO"]),
    ("Gol", [" GOL ", "GOLMEGA", "GOL MINI", "GOLCOCO", "GOLMELO"]),
    ("Tikys", ["TIKYS", "GOLOCHIPS"]),
    ("Montblanc", ["MONTBLANC", "MONT BLANC"]),
    ("Santander", ["SANTANDER"]),
    ("Cordillera", ["CORDILLERA", "COBER SCH"]),
    ("Cordillera", ["CREMA AVELLANA", "COCOA NATURAL", "REPOST."]),
    ("Corona", ["CORONA", "CHOCOL CORONA", "COCOA CORONA"]),
    ("Corona", ["CHOCOL CRUZ", "CRUZ ", "CHOCOL TESALIA", "TESALIA"]),
    ("Lyne", ["CHOCOLYNE", " LYNE "]),
    ("Chocolisto", ["CHOCOLISTO"]),
    ("Tosh", ["TOSH"]),
    ("La Especial", ["LAESPECIAL", "LA ESPECIAL", "PASAB. LE", "MANICERO"]),
    ("Festival", ["FESTIVAL"]),
    ("Festival", ["MINICHIPS"]),
    ("Dux", ["DUX"]),
    ("Ducal", ["DUCALES", "DUCAL"]),
    ("Noel", ["NOEL", "SALTIN", "WAFER NOEL", "TRITON"]),
    ("Doria", ["DORIA"]),
    ("Comarrico", ["COMARRICO"]),
    ("Comarrico", ["COMARRI CO"]),
    ("Monticello", ["MONTICELLO"]),
    ("Badia", ["BADIA"]),
    ("Zenú", ["ZENÚ", "ZENU", "CARVE"]),
    ("Setas", ["CHAMP. SETAS", "SETAS"]),
    ("Zenú", ["ENSALADA MAÍZ", "ENSALADA MAIZ"]),
    ("Rica", ["SALCHICHA VIENA RICA"]),
    ("Benet", ["BENET"]),
]


def brand_for(name: str) -> str:
    probe = f" {name.upper()} "
    for brand, needles in BRAND_RULES:
        if any(needle in probe for needle in needles):
            return brand
    return "Red de Marcas"


def quality(row: dict) -> tuple[int, int]:
    name = row["nombre"]
    score = 0
    if not name.startswith("Producto "):
        score += 20
    if row["marca"] != "Red de Marcas":
        score += 10
    if len(name) > 18:
        score += 5
    if len(name) > 45:
        score -= 2
    return (score, -len(name))


def render(page: fitz.Page, image: ImageItem, output: Path) -> None:
    pixmap = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=image.clip(page.rect), alpha=False)
    pixmap.save(output)


def extract_visual_products(pdf_path: Path) -> tuple[list[dict], list[dict]]:
    doc = fitz.open(pdf_path)
    products: dict[str, dict] = {}
    conflicts: list[dict] = []
    global_order = 1

    PUBLIC_PRODUCTS.mkdir(parents=True, exist_ok=True)

    for page_index, page in enumerate(doc, start=1):
        if page_index in {1, 39}:
            continue

        words = words_for_page(page)
        images = visual_order(product_images(page, page_index))

        for image in images:
            code_word = code_for_image(image, words)
            if not code_word:
                continue

            code = code_word["text"]
            tokens = text_between(image, code_word, words)
            name = normalize_name(tokens, code)
            brand = brand_for(name)
            image_path = f"/productos/{code}.png"

            render(page, image, PUBLIC_PRODUCTS / f"{code}.png")

            row = {
                "orden": str(global_order),
                "pagina": str(page_index),
                "codigo": code,
                "nombre": name,
                "marca": brand,
                "categoria": f"Pagina {page_index}",
                "imagen": image_path,
                "estado": "visual",
            }

            if code in products:
                previous = products[code]
                conflicts.append({**row, "estado": f"duplicado_visual_de_orden_{previous['orden']}"})
                if quality(row) > quality(previous):
                    row["orden"] = previous["orden"]
                    products[code] = row
                continue

            products[code] = row
            global_order += 1

    rows = sorted(products.values(), key=lambda item: int(item["orden"]))
    return rows, conflicts


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def pdf_codes_by_page(pdf_path: Path) -> list[dict]:
    doc = fitz.open(pdf_path)
    rows = []
    for page_index, page in enumerate(doc, start=1):
        seen = set()
        for code in re.findall(r"(?<!\d)\d{6,8}(?!\d)", page.get_text("text")):
            if code in seen:
                continue
            seen.add(code)
            rows.append({"pagina": str(page_index), "codigo": code})
    return rows


def import_db(rows: list[dict]) -> None:
    connection = sqlite3.connect(DB)
    try:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(products)").fetchall()]
        if "sort_order" not in columns:
            connection.execute("ALTER TABLE products ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 999999")

        connection.execute("DELETE FROM products")
        connection.executemany(
            """
            INSERT INTO products (code, name, brand, category, image, sort_order)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["codigo"],
                    row["nombre"],
                    row["marca"],
                    row["categoria"],
                    row["imagen"],
                    int(row["orden"]),
                )
                for row in rows
            ],
        )
        connection.commit()
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--import-db", action="store_true")
    args = parser.parse_args()

    rows, conflicts = extract_visual_products(PDF)
    product_rows = [
        {
            "codigo": row["codigo"],
            "nombre": row["nombre"],
            "marca": row["marca"],
            "categoria": row["categoria"],
            "imagen": row["imagen"],
        }
        for row in rows
    ]
    write_csv(OUT_DIR / "productos_extraidos.csv", product_rows, ["codigo", "nombre", "marca", "categoria", "imagen"])
    write_csv(OUT_DIR / "catalogo_canonico_visual.csv", rows, AUDIT_FIELDS)
    write_csv(OUT_DIR / "duplicados_visuales.csv", conflicts, AUDIT_FIELDS)

    pdf_codes = pdf_codes_by_page(PDF)
    visual_codes = {row["codigo"] for row in rows}
    missing = [
        {"pagina": row["pagina"], "codigo": row["codigo"], "estado": "solo_texto_lista_o_sin_imagen"}
        for row in pdf_codes
        if row["codigo"] not in visual_codes
    ]
    write_csv(OUT_DIR / "codigos_pdf_no_visuales.csv", missing, ["pagina", "codigo", "estado"])

    no_image_rows: list[dict] = []
    doubtful_rows = [
        row for row in product_rows
        if row["nombre"].startswith("Producto ") or row["marca"] == "Red de Marcas"
    ]
    write_csv(OUT_DIR / "productos_sin_imagen.csv", no_image_rows, ["codigo", "nombre", "marca", "categoria", "imagen"])
    write_csv(OUT_DIR / "productos_nombre_dudoso.csv", doubtful_rows, ["codigo", "nombre", "marca", "categoria", "imagen"])

    if args.import_db:
        import_db(rows)

    by_brand: dict[str, int] = {}
    for row in rows:
        by_brand[row["marca"]] = by_brand.get(row["marca"], 0) + 1

    print(f"Productos canonicos visuales: {len(rows)}")
    print(f"Duplicados visuales ignorados: {len(conflicts)}")
    print(f"Codigos solo en texto/listas: {len(missing)}")
    for brand, count in sorted(by_brand.items(), key=lambda item: (-item[1], item[0])):
        print(f"{brand}: {count}")


if __name__ == "__main__":
    main()
