import csv
import shutil
import sqlite3
from pathlib import Path


OUT_DIR = Path("data/extraccion-catalogo")
CANONICAL = OUT_DIR / "catalogo_canonico_visual.csv"
MAIN_CSV = OUT_DIR / "productos_extraidos.csv"
FINAL_AUDIT = OUT_DIR / "catalogo_final_auditado.csv"
EXCLUDED = OUT_DIR / "codigos_lista_excluidos.csv"
DB = Path("data/catalogo.sqlite")
PRODUCTS = Path("public/productos")


JET_ORDER = [
    ("1066741", "Glina. Jet leche 30plex 50un dx11g Encelof #1"),
    ("1066742", "Glina. Jet leche 12plex 24un dx11g Encelof #1"),
    ("1066729", "Glina. Jet leche 18plex 16un dx25g #2"),
    ("1064707", "Glina. Jet leche 24plex 22un dx45g #3"),
    ("1003844", "Glina. Jet leche calcio 12plex 24un dx12g"),
    ("1064641", "Glina. Jet fresaCrema 12plex 12un dx29g"),
    ("1004068", "Glina. Jet Blanca 24plex 18un dx24g"),
    ("1036847", "Glina. Jet Burbujet 18plex 6un dx50g"),
    ("1042138", "Glina. Jet Burbujet C&C 18plex 4un dx50g"),
    ("1036562", "Glina. Jet Crema Stick 8plex 12un dx8g"),
    ("1021370", "Glina. Jet Cookies&Cream 18plex 6un dx50g"),
    ("1032475", "Glina. Jet Cookies&Cream 11plex 10un dx21g"),
    ("1024739", "Glina. Jet Cookies&Cream 24plex 24un dx11g"),
    ("1004071", "Glina. Jet leche 24bol 24un dx6g"),
    ("1004077", "Glina. Jet sabor surtido 24bol 24un dx6g"),
    ("1015400", "Glina. Jet calcio 48bol 12un dx 12g"),
    ("1003837", "Glina. Jet Lyne 12bol 24un dx 9g"),
    ("1025339", "Glina. Jet Burbujas 24bol 12un dx 14g"),
    ("1055521", "Glina. Jet Burbujas C&C 24bol 12un dx 13.2g"),
    ("1070593", "Glina. Jet caramel 24bol 18un dx 6g"),
    ("1047512", "Glina. Jet crema 32 und 140g"),
    ("1027117", "Glina. Jet Wafer surtida 20bol 20un dx 22g"),
    ("1003905", "Glina. Jet Wafer Vainilla 20bol 20un dx 22g"),
    ("1003907", "Glina. Jet Wafer Vainilla 40bol 10un dx 22g"),
    ("1025338", "Glina. Jet Gool balones 12bol 100un dx 4.5g"),
    ("1025337", "Glina. Jet Gool balones 24bol 18un dx 4.5g"),
    ("2013824", "Album Jet Colombia Sorprendente Exh5"),
]


REPLACE_CODES = {
    "1069598": {
        "codigo": "1063538",
        "nombre": "Chocol. Chocolyne Clas. 24bol x200g",
        "marca": "Lyne",
        "motivo": "La lista sin imagen corrige el codigo del clasico x200g.",
    },
    "1078718": {
        "codigo": "1075718",
        "nombre": "Gta.Noel Wafers Coco Bs. 12x2",
        "marca": "Noel",
        "motivo": "La lista sin imagen corrige el codigo de Wafer Noel Coco.",
    },
    "2006353": {
        "codigo": "2006359",
        "nombre": "Salsa Monticello Napoletana x400g",
        "marca": "Monticello",
        "motivo": "La lista sin imagen corrige el codigo de Napoletana.",
    },
}


ADD_AFTER = [
    {
        "after": "1056484",
        "codigo": "1039804",
        "nombre": "Glina. Montblanc FresBlan Granel 40ux80g",
        "marca": "Montblanc",
        "categoria": "Pagina 12",
        "source_image": "1056484",
        "motivo": "Codigo de Fresa Blanca aparece en lista; el visual repetia 1056484.",
    },
    {
        "after": "1037498",
        "codigo": "1037497",
        "nombre": "Repost. Corona M.G Lech7 Dep 24bolx500g",
        "marca": "Corona",
        "categoria": "Pagina 15",
        "source_image": "1037498",
        "motivo": "Codigo de cobertura leche aparece en lista; el visual repetia 1037498.",
    },
    {
        "after": "1076740",
        "codigo": "1075622",
        "nombre": "Modif. Chocolisto 12tar x900g",
        "marca": "Chocolisto",
        "categoria": "Pagina 18",
        "source_image": "1076740",
        "motivo": "Codigo de tarro 900g aparece en lista; el visual repetia 1076740.",
    },
    {
        "after": "2031245",
        "codigo": "2031244",
        "nombre": "Infu. Tosh Frutos Rojos 20und",
        "marca": "Tosh",
        "categoria": "Pagina 21",
        "source_image": "2031245",
        "motivo": "Variante 20und incluida en el bloque visual como texto sin imagen propia.",
    },
    {
        "after": "2031415",
        "codigo": "2031414",
        "nombre": "Arom. Tosh ManzanLimonJeng 20und",
        "marca": "Tosh",
        "categoria": "Pagina 21",
        "source_image": "2031415",
        "motivo": "Variante 20und incluida en el bloque visual como texto sin imagen propia.",
    },
    {
        "after": "2016782",
        "codigo": "2019815",
        "nombre": "Aceite de Coco Extra Virgen Monticello x360g",
        "marca": "Monticello",
        "categoria": "Pagina 33",
        "source_image": "2016782",
        "motivo": "Codigo de aceite de coco 360g aparece en lista; el visual repetia 2016782.",
    },
]


EXCLUDED_CODES = [
    ("9", "102538", "Jet Gool x100un: codigo truncado en lista; se conserva visual 1025338."),
    ("9", "102537", "Jet Gool x18un: codigo truncado en lista; se conserva visual 1025337."),
    ("11", "1068246", "Gol x15un en lista difiere del visual; se conserva visual 1068249."),
    ("11", "1068853", "Gol Melo en lista difiere del visual; se conserva visual 1069946."),
    ("30", "1001570", "Spaghetti Multicereal 250g aparece solo en lista sin imagen; se conserva visual 1001470 de 500g."),
]


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def copy_image(source_code: str, target_code: str) -> str:
    source = PRODUCTS / f"{source_code}.png"
    target = PRODUCTS / f"{target_code}.png"
    if source.exists() and not target.exists():
        shutil.copyfile(source, target)
    return f"/productos/{target_code}.png"


def normalize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized = []
    for row in rows:
        next_row = dict(row)
        next_row["orden_num"] = float(row["orden"])

        if next_row["codigo"] in REPLACE_CODES:
            replacement = REPLACE_CODES[next_row["codigo"]]
            old_code = next_row["codigo"]
            next_row["codigo"] = replacement["codigo"]
            next_row["nombre"] = replacement["nombre"]
            next_row["marca"] = replacement["marca"]
            next_row["imagen"] = copy_image(old_code, replacement["codigo"])
            next_row["estado"] = f"corregido_codigo: {replacement['motivo']}"

        if next_row["codigo"] == "1037498":
            next_row["nombre"] = "Repost. Corona M.G Blanca Dep 24bolx500g"
            next_row["marca"] = "Corona"
            next_row["estado"] = "corregido_nombre_marca"

        if next_row["codigo"] == "1056484":
            next_row["nombre"] = "Glina. Montblanc Baileys blan 12plex 6ux42g"
            next_row["marca"] = "Montblanc"
            next_row["estado"] = "corregido_nombre"

        if next_row["codigo"] == "1076740":
            next_row["nombre"] = "Modif. Chocolisto 30tar x300g"
            next_row["marca"] = "Chocolisto"
            next_row["estado"] = "corregido_nombre"

        if next_row["codigo"] == "2016782":
            next_row["nombre"] = "Salsa Monticello Alfredo x410g"
            next_row["marca"] = "Monticello"
            next_row["estado"] = "corregido_nombre"

        if next_row["codigo"] in {"1008490", "1003876"}:
            next_row["marca"] = "Corona"

        normalized.append(next_row)

    by_code = {row["codigo"]: row for row in normalized}
    for addition in ADD_AFTER:
        if addition["codigo"] in by_code:
            continue
        base = by_code.get(addition["after"])
        if not base:
            continue
        new_row = {
            "orden": "",
            "orden_num": float(base["orden_num"]) + 0.1,
            "pagina": base["pagina"],
            "codigo": addition["codigo"],
            "nombre": addition["nombre"],
            "marca": addition["marca"],
            "categoria": addition["categoria"],
            "imagen": copy_image(addition["source_image"], addition["codigo"]),
            "estado": f"agregado_desde_lista: {addition['motivo']}",
        }
        normalized.append(new_row)
        by_code[new_row["codigo"]] = new_row

    normalized = [row for row in normalized if row["codigo"] not in {"102537", "102538"}]
    normalized.sort(key=lambda row: (float(row["orden_num"]), row["codigo"]))

    for index, row in enumerate(normalized, start=1):
        row["orden"] = str(index)
        row["orden_num"] = str(index)

    return normalized


def apply_jet(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_code = {row["codigo"]: row for row in rows}
    jet_codes = [code for code, _ in JET_ORDER]
    first_jet_order = min(float(by_code[code]["orden_num"]) for code in jet_codes if code in by_code)

    for offset, (code, name) in enumerate(JET_ORDER):
        row = by_code.get(code)
        if not row:
            continue
        row["nombre"] = name
        row["marca"] = "Jet"
        row["categoria"] = "Pagina 8" if offset < 20 else "Pagina 9"
        row["imagen"] = f"/productos/{code}.png"
        row["orden_num"] = str(first_jet_order + offset / 100)
        row["estado"] = "jet_auditado_manual"

    rows.sort(key=lambda row: (float(row["orden_num"]), row["codigo"]))
    for index, row in enumerate(rows, start=1):
        row["orden"] = str(index)
        row["orden_num"] = str(index)
    return rows


def import_db(rows: list[dict[str, str]]) -> None:
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
                (row["codigo"], row["nombre"], row["marca"], row["categoria"], row["imagen"], int(row["orden"]))
                for row in rows
            ],
        )
        connection.commit()
    finally:
        connection.close()


def main() -> None:
    rows = normalize_rows(load_rows(CANONICAL))
    rows = apply_jet(rows)

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
    write_rows(MAIN_CSV, product_rows, ["codigo", "nombre", "marca", "categoria", "imagen"])
    write_rows(FINAL_AUDIT, rows, ["orden", "pagina", "codigo", "nombre", "marca", "categoria", "imagen", "estado"])
    write_rows(
        EXCLUDED,
        [{"pagina": page, "codigo": code, "motivo": reason} for page, code, reason in EXCLUDED_CODES],
        ["pagina", "codigo", "motivo"],
    )
    write_rows(OUT_DIR / "productos_sin_imagen.csv", [], ["codigo", "nombre", "marca", "categoria", "imagen"])
    write_rows(
        OUT_DIR / "productos_nombre_dudoso.csv",
        [row for row in product_rows if row["nombre"].startswith("Producto ") or row["marca"] == "Red de Marcas"],
        ["codigo", "nombre", "marca", "categoria", "imagen"],
    )
    import_db(rows)
    print(f"Catalogo final: {len(rows)} productos")
    print(f"Auditoria final: {FINAL_AUDIT}")
    print(f"Codigos excluidos de listas sin imagen: {len(EXCLUDED_CODES)}")


if __name__ == "__main__":
    main()
