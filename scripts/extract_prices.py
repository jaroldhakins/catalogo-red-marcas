import csv
import re
import sqlite3
from pathlib import Path

import fitz


PDF = Path("Catalogo completo Red de Marcas-1.pdf")
AUDIT = Path("data/extraccion-catalogo/catalogo_final_auditado.csv")
MAIN_CSV = Path("data/extraccion-catalogo/productos_extraidos.csv")
PRICE_AUDIT = Path("data/extraccion-catalogo/precios_auditados.csv")
PRICE_CONFLICTS = Path("data/extraccion-catalogo/precios_conflictos.csv")
PRICE_MISSING = Path("data/extraccion-catalogo/precios_faltantes.csv")
DB = Path("data/catalogo.sqlite")

CODE_RE = re.compile(r"^\d{6,8}$")
PRICE_RE = re.compile(r"^\$?\d{1,3}(?:[.,]\d{3})+$|^\$?\d{4,7}$")

PRICE_OVERRIDES = {
    "1037672": (12549, "override_visual: precio correcto junto al producto"),
    "1003294": (31250, "override_visual: precio correcto junto al producto"),
    "1056679": (10002, "override_pdf: lista/visual de Colcafe granulado 1.5g"),
    "1003353": (24081, "override_pdf: producto auditado es frasco 170g"),
    "1003355": (11583, "override_pdf: frasco 50g"),
    "1002807": (24500, "override_pdf: clasico x25g x6 sobres"),
    "1058531": (33433, "override_pdf: Jumbo Brownie mini"),
    "1055760": (15737, "override_pdf: Santander Amarga 70%"),
    "1063338": (45375, "override_pdf: Chocolatina Lyne x12Un"),
    "1063339": (13750, "override_pdf: Chocolatina Lyne x18Un"),
    "1064999": (7200, "override_pdf: producto auditado Fusion Cereal 9x3"),
    "1059670": (8018, "override_pdf: Tosh Miel taco x2"),
    "1039634": (8960, "override_pdf: producto auditado Hierbabuena"),
    "1053045": (4180, "override_pdf: Te Tosh Negro"),
    "1047411": (7917, "override_pdf: Manzanilla Anis Menta"),
    "1077768": (8160, "override_pdf: Dux Ranchera queso fundido"),
    "1005133": (1533, "override_pdf: Fideo Comarrico 250g"),
    "1008690": (1533, "override_pdf: producto auditado Coditos 250g"),
    "2030793": (10710, "override_pdf: Aceite oliva x100ml"),
    "2019814": (28620, "override_pdf: Aceite aguacate x250ml"),
    "1004945": (30366, "override_pdf: Setas Tajado 3000g"),
    "2019270": (22330, "override_pdf: Gomas Benet VitC"),
    "1025338": (31990, "override_pdf: Jet Gool x100un listado como 102538"),
    "1068249": (18004, "override_pdf: Gol x15un listado como 1068246"),
    "1069946": (3198, "override_pdf: Gol Melo listado como 1068853"),
    "1022145": (2289, "override_pdf: Spaghetti chorizo listado con codigo duplicado 1014738"),
}


def parse_price(value: str) -> int | None:
    if "$" not in value:
        return None
    text = value.strip().replace("$", "").replace(" ", "")
    if not PRICE_RE.match(text):
        return None
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    price = int(digits)
    if price < 100:
        return None
    return price


def load_catalog() -> list[dict[str, str]]:
    with AUDIT.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


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
    words.sort(key=lambda item: (item["block"], item["line"], item["word"], item["y0"], item["x0"]))
    return words


def sequential_prices(doc: fitz.Document) -> dict[str, list[dict]]:
    matches: dict[str, list[dict]] = {}
    for page_number, page in enumerate(doc, start=1):
        pending_code = None
        for word in words_for_page(page):
            token = word["text"]
            if CODE_RE.match(token):
                pending_code = token
                continue
            price = parse_price(token)
            if price is not None and pending_code:
                matches.setdefault(pending_code, []).append({
                    "codigo": pending_code,
                    "precio": price,
                    "pagina": str(page_number),
                    "fuente": "secuencial_codigo_precio",
                    "x": f"{word['cx']:.1f}",
                    "y": f"{word['cy']:.1f}",
                })
                pending_code = None
    return matches


def visual_prices(doc: fitz.Document, catalog: list[dict[str, str]]) -> dict[str, list[dict]]:
    matches: dict[str, list[dict]] = {}
    by_page: dict[int, list[str]] = {}
    for row in catalog:
        by_page.setdefault(int(row["pagina"]), []).append(row["codigo"])

    for page_number, codes in by_page.items():
        page = doc[page_number - 1]
        words = words_for_page(page)
        code_words = [word for word in words if word["text"] in codes]
        price_words = [(word, parse_price(word["text"])) for word in words]
        price_words = [(word, price) for word, price in price_words if price is not None]

        for code_word in code_words:
            code = code_word["text"]
            candidates = []
            for price_word, price in price_words:
                horizontal = abs(price_word["cx"] - code_word["cx"])
                vertical = price_word["cy"] - code_word["cy"]
                if horizontal <= 70 and 0 <= vertical <= 45:
                    candidates.append((horizontal + vertical, price_word, price))
            if not candidates:
                continue
            candidates.sort(key=lambda item: item[0])
            _, price_word, price = candidates[0]
            matches.setdefault(code, []).append({
                "codigo": code,
                "precio": price,
                "pagina": str(page_number),
                "fuente": "visual_cercano",
                "x": f"{price_word['cx']:.1f}",
                "y": f"{price_word['cy']:.1f}",
            })
    return matches


def choose_prices(catalog: list[dict[str, str]], all_matches: dict[str, list[dict]]) -> tuple[list[dict], list[dict], list[dict]]:
    audited = []
    conflicts = []
    missing = []

    for row in catalog:
        code = row["codigo"]
        matches = all_matches.get(code, [])
        prices = sorted(set(match["precio"] for match in matches))
        override = PRICE_OVERRIDES.get(code)

        if override:
            price = override[0]
            matches = matches + [{
                "codigo": code,
                "precio": price,
                "pagina": row["pagina"],
                "fuente": override[1],
            }]
        elif not prices:
            price = 0
            missing.append({"codigo": code, "nombre": row["nombre"], "marca": row["marca"], "pagina": row["pagina"]})
        elif len(prices) == 1:
            price = prices[0]
        else:
            # Prefer the most frequent value; if tied, prefer visual source.
            ranked = []
            for candidate in prices:
                same = [match for match in matches if match["precio"] == candidate]
                visual_count = sum(1 for match in same if match["fuente"] == "visual_cercano")
                ranked.append((len(same), visual_count, candidate))
            ranked.sort(reverse=True)
            price = ranked[0][2]
            conflicts.append({
                "codigo": code,
                "nombre": row["nombre"],
                "marca": row["marca"],
                "pagina": row["pagina"],
                "precio_elegido": str(price),
                "precios_detectados": " | ".join(str(value) for value in prices),
                "fuentes": " | ".join(f"{m['fuente']}:{m['precio']}:p{m['pagina']}" for m in matches),
            })

        audited.append({
            **row,
            "precio": str(price),
            "fuentes_precio": " | ".join(f"{m['fuente']}:{m['precio']}:p{m['pagina']}" for m in matches),
        })

    return audited, conflicts, missing


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def update_main_csv(rows: list[dict]) -> None:
    write_csv(
        MAIN_CSV,
        [
            {
                "codigo": row["codigo"],
                "nombre": row["nombre"],
                "marca": row["marca"],
                "categoria": row["categoria"],
                "imagen": row["imagen"],
                "precio": row["precio"],
            }
            for row in rows
        ],
        ["codigo", "nombre", "marca", "categoria", "imagen", "precio"],
    )


def update_db(rows: list[dict]) -> None:
    connection = sqlite3.connect(DB)
    try:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(products)").fetchall()]
        if "price" not in columns:
            connection.execute("ALTER TABLE products ADD COLUMN price INTEGER NOT NULL DEFAULT 0")
        connection.executemany(
            "UPDATE products SET price = ? WHERE code = ?",
            [(int(row["precio"]), row["codigo"]) for row in rows],
        )
        connection.commit()
    finally:
        connection.close()


def main() -> None:
    catalog = load_catalog()
    doc = fitz.open(PDF)
    matches: dict[str, list[dict]] = {}
    for source in [sequential_prices(doc), visual_prices(doc, catalog)]:
        for code, items in source.items():
            matches.setdefault(code, []).extend(items)

    audited, conflicts, missing = choose_prices(catalog, matches)
    write_csv(PRICE_AUDIT, audited, [
        "orden", "pagina", "codigo", "nombre", "marca", "categoria", "imagen", "precio", "estado", "fuentes_precio"
    ])
    write_csv(PRICE_CONFLICTS, conflicts, [
        "codigo", "nombre", "marca", "pagina", "precio_elegido", "precios_detectados", "fuentes"
    ])
    write_csv(PRICE_MISSING, missing, ["codigo", "nombre", "marca", "pagina"])
    update_main_csv(audited)
    update_db(audited)

    print(f"Productos con precio auditado: {len(audited)}")
    print(f"Conflictos de precio: {len(conflicts)}")
    print(f"Precios faltantes: {len(missing)}")
    print(f"Auditoria: {PRICE_AUDIT}")


if __name__ == "__main__":
    main()
