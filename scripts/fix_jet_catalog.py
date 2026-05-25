import csv
import sqlite3
from pathlib import Path

import fitz


PDF = Path("Catalogo completo Red de Marcas-1.pdf")
MAIN_CSV = Path("data/extraccion-catalogo/productos_extraidos.csv")
NO_IMAGE_CSV = Path("data/extraccion-catalogo/productos_sin_imagen.csv")
DOUBTFUL_CSV = Path("data/extraccion-catalogo/productos_nombre_dudoso.csv")
AUDIT_CSV = Path("data/extraccion-catalogo/auditoria_jet.csv")
DB = Path("data/catalogo.sqlite")
PUBLIC_PRODUCTS = Path("public/productos")


JET_PRODUCTS = [
    {"codigo": "1066741", "nombre": "Glina. Jet leche 30plex 50un dx11g Encelof #1", "pagina": "Pagina 8"},
    {"codigo": "1066742", "nombre": "Glina. Jet leche 12plex 24un dx11g Encelof #1", "pagina": "Pagina 8"},
    {"codigo": "1066729", "nombre": "Glina. Jet leche 18plex 16un dx25g #2", "pagina": "Pagina 8"},
    {"codigo": "1064707", "nombre": "Glina. Jet leche 24plex 22un dx45g #3", "pagina": "Pagina 8"},
    {"codigo": "1003844", "nombre": "Glina. Jet leche calcio 12plex 24un dx12g", "pagina": "Pagina 8"},
    {"codigo": "1064641", "nombre": "Glina. Jet fresaCrema 12plex 12un dx29g", "pagina": "Pagina 8"},
    {"codigo": "1004068", "nombre": "Glina. Jet Blanca 24plex 18un dx24g", "pagina": "Pagina 8"},
    {"codigo": "1036847", "nombre": "Glina. Jet Burbujet 18plex 6un dx50g", "pagina": "Pagina 8"},
    {"codigo": "1042138", "nombre": "Glina. Jet Burbujet C&C 18plex 4un dx50g", "pagina": "Pagina 8"},
    {"codigo": "1036562", "nombre": "Glina. Jet Crema Stick 8plex 12un dx8g", "pagina": "Pagina 8"},
    {"codigo": "1021370", "nombre": "Glina. Jet Cookies&Cream 18plex 6un dx50g", "pagina": "Pagina 8"},
    {"codigo": "1032475", "nombre": "Glina. Jet Cookies&Cream 11plex 10un dx21g", "pagina": "Pagina 8"},
    {"codigo": "1024739", "nombre": "Glina. Jet Cookies&Cream 24plex 24un dx11g", "pagina": "Pagina 8"},
    {"codigo": "1004071", "nombre": "Glina. Jet leche 24bol 24un dx6g", "pagina": "Pagina 8"},
    {"codigo": "1004077", "nombre": "Glina. Jet sabor surtido 24bol 24un dx6g", "pagina": "Pagina 8"},
    {"codigo": "1015400", "nombre": "Glina. Jet calcio 48bol 12un dx 12g", "pagina": "Pagina 8"},
    {"codigo": "1003837", "nombre": "Glina. Jet Lyne 12bol 24un dx 9g", "pagina": "Pagina 8"},
    {"codigo": "1025339", "nombre": "Glina. Jet Burbujas 24bol 12un dx 14g", "pagina": "Pagina 8"},
    {"codigo": "1055521", "nombre": "Glina. Jet Burbujas C&C 24bol 12un dx 13.2g", "pagina": "Pagina 8"},
    {"codigo": "1070593", "nombre": "Glina. Jet caramel 24bol 18un dx 6g", "pagina": "Pagina 8"},
    {"codigo": "1047512", "nombre": "Glina. Jet crema 32 und 140g", "pagina": "Pagina 9"},
    {"codigo": "1027117", "nombre": "Glina. Jet Wafer surtida 20bol 20un dx 22g", "pagina": "Pagina 9"},
    {"codigo": "1003905", "nombre": "Glina. Jet Wafer Vainilla 20bol 20un dx 22g", "pagina": "Pagina 9"},
    {"codigo": "1003907", "nombre": "Glina. Jet Wafer Vainilla 40bol 10un dx 22g", "pagina": "Pagina 9"},
    {"codigo": "1025338", "nombre": "Glina. Jet Gool balones 12bol 100un dx 4.5g", "pagina": "Pagina 9"},
    {"codigo": "1025337", "nombre": "Glina. Jet Gool balones 24bol 18un dx 4.5g", "pagina": "Pagina 9"},
    {"codigo": "2013824", "nombre": "Album Jet Colombia Sorprendente Exh5", "pagina": "Pagina 9"},
]


PAGE_9_CROPS = {
    "1047512": (179.1, 140.8, 254.9, 230.9),
    "1027117": (319.8, 164.3, 419.6, 222.1),
    "1003905": (475.5, 166.3, 564.1, 220.3),
    "1003907": (179.1, 305.1, 238.4, 396.6),
    "1025338": (274.8, 331.1, 360.3, 403.1),
    "1025337": (395.0, 336.9, 461.8, 396.9),
    "2013824": (489.9, 329.6, 577.0, 397.1),
}


REMOVED_DUPLICATES = {"102537", "102538"}


def render_page_9_images() -> None:
    PUBLIC_PRODUCTS.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(PDF)
    page = doc[8]
    for code, bbox in PAGE_9_CROPS.items():
        rect = fitz.Rect(*bbox)
        rect = fitz.Rect(
            max(0, rect.x0 - 8),
            max(0, rect.y0 - 8),
            min(page.rect.width, rect.x1 + 8),
            min(page.rect.height, rect.y1 + 8),
        )
        pixmap = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=rect, alpha=False)
        pixmap.save(PUBLIC_PRODUCTS / f"{code}.png")


def canonical_rows() -> dict[str, dict[str, str]]:
    return {
        item["codigo"]: {
            "codigo": item["codigo"],
            "nombre": item["nombre"],
            "marca": "Jet",
            "categoria": item["pagina"],
            "imagen": f"/productos/{item['codigo']}.png",
            "orden": str(index + 1),
        }
        for index, item in enumerate(JET_PRODUCTS)
    }


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["codigo", "nombre", "marca", "categoria", "imagen"])
        writer.writeheader()
        writer.writerows(rows)


def update_main_csv(canonical: dict[str, dict[str, str]]) -> None:
    rows = load_csv(MAIN_CSV)
    non_jet = [
        row for row in rows
        if row.get("marca") != "Jet" and row.get("codigo") not in REMOVED_DUPLICATES
    ]
    updated = non_jet + [
        {key: row[key] for key in ["codigo", "nombre", "marca", "categoria", "imagen"]}
        for row in canonical.values()
    ]
    updated.sort(key=lambda row: (row["categoria"], row["marca"], row["nombre"], row["codigo"]))
    write_csv(MAIN_CSV, updated)


def update_review_csvs(canonical: dict[str, dict[str, str]]) -> None:
    canonical_codes = set(canonical)
    for path in [NO_IMAGE_CSV, DOUBTFUL_CSV]:
        rows = load_csv(path)
        rows = [
            row for row in rows
            if row.get("codigo") not in canonical_codes and row.get("codigo") not in REMOVED_DUPLICATES
        ]
        write_csv(path, rows)


def update_database(canonical: dict[str, dict[str, str]]) -> None:
    connection = sqlite3.connect(DB)
    try:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(products)").fetchall()]
        if "sort_order" not in columns:
            connection.execute("ALTER TABLE products ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 999999")

        connection.executemany("DELETE FROM products WHERE code = ?", [(code,) for code in REMOVED_DUPLICATES])
        connection.executemany(
            """
            INSERT INTO products (code, name, brand, category, image, sort_order)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
              name = excluded.name,
              brand = excluded.brand,
              category = excluded.category,
              image = excluded.image,
              sort_order = excluded.sort_order
            """,
            [
                (row["codigo"], row["nombre"], row["marca"], row["categoria"], row["imagen"], int(row["orden"]))
                for row in canonical.values()
            ],
        )
        connection.commit()
    finally:
        connection.close()


def write_audit(canonical: dict[str, dict[str, str]]) -> None:
    rows = list(canonical.values())
    rows.sort(key=lambda row: int(row["orden"]))
    with AUDIT_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["orden", "codigo", "nombre", "marca", "categoria", "imagen"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    canonical = canonical_rows()
    if len(canonical) != 27:
        raise RuntimeError(f"Jet debe tener 27 productos, no {len(canonical)}")

    render_page_9_images()
    update_main_csv(canonical)
    update_review_csvs(canonical)
    update_database(canonical)
    write_audit(canonical)

    print("Jet corregido: 27 productos canonicos")
    print(f"Auditoria: {AUDIT_CSV}")


if __name__ == "__main__":
    main()
