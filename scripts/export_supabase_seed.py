import sqlite3
from pathlib import Path


DB = Path("data/catalogo.sqlite")
OUT = Path("supabase/seed_products.sql")


def sql(value):
    if value is None:
        return "null"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


connection = sqlite3.connect(DB)
rows = connection.execute(
    """
    SELECT code, name, brand, category, image, price, sort_order
    FROM products
    ORDER BY sort_order, brand, name
    """
).fetchall()
connection.close()

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", encoding="utf-8") as file:
    file.write("insert into public.products (code, name, brand, category, image, price, sort_order) values\n")
    values = []
    for row in rows:
        values.append("(" + ", ".join(sql(value) for value in row) + ")")
    file.write(",\n".join(values))
    file.write(
        "\non conflict (code) do update set\n"
        "  name = excluded.name,\n"
        "  brand = excluded.brand,\n"
        "  category = excluded.category,\n"
        "  image = excluded.image,\n"
        "  price = excluded.price,\n"
        "  sort_order = excluded.sort_order,\n"
        "  updated_at = now();\n"
    )

print(f"Productos exportados: {len(rows)}")
print(f"Archivo: {OUT}")
