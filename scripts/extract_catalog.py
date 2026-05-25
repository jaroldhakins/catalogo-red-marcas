import argparse
import csv
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import fitz


PDF_NAME = "Catalogo completo Red de Marcas-1.pdf"
CODE_PATTERN = re.compile(r"^\d{6,8}$")
PRICE_PATTERN = re.compile(r"^\$?[\d.,]+$")


@dataclass
class RectItem:
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

    def expanded(self, padding: float, page_rect: fitz.Rect) -> fitz.Rect:
        return fitz.Rect(
            max(0, self.x0 - padding),
            max(0, self.y0 - padding),
            min(page_rect.width, self.x1 + padding),
            min(page_rect.height, self.y1 + padding),
        )


def clean_text(value: str) -> str:
    return " ".join(value.replace("\n", " ").split()).strip()


def normalize_name(words: list[str]) -> str:
    ignored = {
        "pqt",
        "pqt.",
        "un",
        "sob",
        "x",
        "red",
        "de",
        "marcas",
    }
    cleaned = []
    for word in words:
        token = word.strip()
        lower = token.lower()
        if not token:
            continue
        if CODE_PATTERN.match(token) or PRICE_PATTERN.match(token):
            continue
        if lower in ignored:
            continue
        cleaned.append(token)

    result = clean_text(" ".join(cleaned))
    result = re.sub(r"\s+", " ", result)
    return result[:120]


def guess_brand(name: str) -> str:
    upper_name = name.upper()
    known = [
        "BASTILLA",
        "SELLO ROJO",
        "MATIZ",
        "COLCAFE",
        "ZENÚ",
        "ZENU",
        "RICA",
        "PIETRAN",
        "RANCHERA",
        "DUCAL",
        "NOEL",
        "FESTIVAL",
        "JET",
        "CHOCOLISTO",
        "CORONA",
        "DIANA",
        "TOSH",
        "POZUELO",
        "DORIA",
        "MONTICELLO",
        "PASTAS COMARRICO",
        "COMARRICO",
        "SALTIN",
        "TRITON",
    ]
    for brand in known:
        if brand in upper_name:
            return brand.title()
    parts = name.split()
    return parts[1].title() if len(parts) > 1 and parts[0].lower() in {"cafe", "galletas", "chocolate"} else "Red de Marcas"


def useful_images(page: fitz.Page, page_index: int) -> list[RectItem]:
    images = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 1:
            continue
        rect = RectItem(page_index, *block["bbox"])
        if rect.width < 24 or rect.height < 24:
            continue
        if rect.area > 45_000:
            continue
        # Side/background strips repeat on some pages and are not product photos.
        if rect.width > 130 and rect.height > 250:
            continue
        images.append(rect)
    return images


def words_for_page(page: fitz.Page) -> list[dict]:
    words = []
    for raw in page.get_text("words"):
        x0, y0, x1, y1, text, block, line, word = raw[:8]
        words.append({
            "x0": x0,
            "y0": y0,
            "x1": x1,
            "y1": y1,
            "text": text,
            "block": block,
            "line": line,
            "word": word,
        })
    return words


def nearest_image(code_word: dict, images: list[RectItem]) -> RectItem | None:
    code_x = (code_word["x0"] + code_word["x1"]) / 2
    code_y = (code_word["y0"] + code_word["y1"]) / 2
    candidates = []
    for image in images:
        horizontal_distance = abs(image.cx - code_x)
        vertical_distance = code_y - image.cy
        if horizontal_distance > 85:
            continue
        if vertical_distance < -25 or vertical_distance > 190:
            continue
        candidates.append((horizontal_distance * 1.3 + abs(vertical_distance - 70), image))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def name_near_code(code_word: dict, image: RectItem | None, words: list[dict]) -> str:
    code_x = (code_word["x0"] + code_word["x1"]) / 2
    if image:
        left = max(0, min(image.x0, code_word["x0"]) - 38)
        right = max(image.x1, code_word["x1"]) + 38
        top = image.y1 - 6
        bottom = code_word["y0"] + 5
    else:
        left = code_x - 90
        right = code_x + 90
        top = code_word["y0"] - 46
        bottom = code_word["y0"] + 5

    nearby = [
        word
        for word in words
        if left <= ((word["x0"] + word["x1"]) / 2) <= right
        and top <= ((word["y0"] + word["y1"]) / 2) <= bottom
        and word["text"] != code_word["text"]
    ]
    nearby.sort(key=lambda word: (word["y0"], word["x0"]))
    name = normalize_name([word["text"] for word in nearby])
    return name or f"Producto {code_word['text']}"


def render_crop(page: fitz.Page, rect: fitz.Rect, output: Path) -> None:
    matrix = fitz.Matrix(3, 3)
    pixmap = page.get_pixmap(matrix=matrix, clip=rect, alpha=False)
    pixmap.save(output)


def extract_catalog(pdf_path: Path, output_dir: Path) -> list[dict]:
    image_dir = output_dir / "imagenes"
    image_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    products: dict[str, dict] = {}

    for page_index, page in enumerate(doc):
        if page_index == 0:
            continue

        images = useful_images(page, page_index)
        words = words_for_page(page)
        code_words = [word for word in words if CODE_PATTERN.match(word["text"])]

        for code_word in code_words:
            code = code_word["text"]
            if code in products:
                continue

            image = nearest_image(code_word, images)
            name = name_near_code(code_word, image, words)
            brand = guess_brand(name)
            category = f"Pagina {page_index + 1}"
            image_path = "/productos/placeholder.svg"

            if image:
                file_name = f"{code}.png"
                render_crop(page, image.expanded(8, page.rect), image_dir / file_name)
                image_path = f"/productos/{file_name}"

            products[code] = {
                "codigo": code,
                "nombre": name,
                "marca": brand,
                "categoria": category,
                "imagen": image_path,
            }

    return sorted(products.values(), key=lambda item: (item["categoria"], item["marca"], item["nombre"], item["codigo"]))


def write_csv(products: list[dict], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["codigo", "nombre", "marca", "categoria", "imagen"])
        writer.writeheader()
        writer.writerows(products)


def write_review_files(products: list[dict], output_dir: Path) -> None:
    without_image = [
        product for product in products
        if product["imagen"] == "/productos/placeholder.svg"
    ]
    short_names = [
        product for product in products
        if product["nombre"].startswith("Producto ") or len(product["nombre"]) < 8
    ]

    write_csv(without_image, output_dir / "productos_sin_imagen.csv")
    write_csv(short_names, output_dir / "productos_nombre_dudoso.csv")


def copy_images_to_public(extraction_dir: Path, public_dir: Path) -> int:
    public_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for image in (extraction_dir / "imagenes").glob("*.png"):
        target = public_dir / image.name
        target.write_bytes(image.read_bytes())
        count += 1
    return count


def import_to_db(products: list[dict], db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS products (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              code TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,
              brand TEXT NOT NULL DEFAULT '',
              category TEXT NOT NULL DEFAULT '',
              image TEXT NOT NULL DEFAULT ''
            )
        """)
        connection.executemany(
            """
            INSERT INTO products (code, name, brand, category, image)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
              name = excluded.name,
              brand = excluded.brand,
              category = excluded.category,
              image = excluded.image
            """,
            [
                (
                    product["codigo"],
                    product["nombre"],
                    product["marca"],
                    product["categoria"],
                    product["imagen"],
                )
                for product in products
            ],
        )
        connection.commit()
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrae productos del catalogo PDF.")
    parser.add_argument("--pdf", default=PDF_NAME)
    parser.add_argument("--out", default="data/extraccion-catalogo")
    parser.add_argument("--public-products", default="public/productos")
    parser.add_argument("--db", default="data/catalogo.sqlite")
    parser.add_argument("--import-db", action="store_true")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    output_dir = Path(args.out)
    products = extract_catalog(pdf_path, output_dir)
    csv_path = output_dir / "productos_extraidos.csv"
    write_csv(products, csv_path)
    write_review_files(products, output_dir)
    copied = copy_images_to_public(output_dir, Path(args.public_products))

    if args.import_db:
        import_to_db(products, Path(args.db))

    print(f"Productos extraidos: {len(products)}")
    print(f"Imagenes copiadas: {copied}")
    print(f"CSV: {csv_path}")
    print(f"Revision sin imagen: {output_dir / 'productos_sin_imagen.csv'}")
    print(f"Revision nombres dudosos: {output_dir / 'productos_nombre_dudoso.csv'}")
    if args.import_db:
        print(f"Base actualizada: {args.db}")


if __name__ == "__main__":
    main()
