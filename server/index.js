import { createServer } from "node:http";
import { readFileSync, existsSync, mkdirSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { DatabaseSync } from "node:sqlite";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const rootDir = resolve(__dirname, "..");
const dataDir = join(rootDir, "data");
const publicDir = join(rootDir, "public");
const distDir = join(rootDir, "dist");
const dbPath = join(dataDir, "catalogo.sqlite");
const deletePin = process.env.DELETE_ORDERS_PIN || "0000";

mkdirSync(dataDir, { recursive: true });
mkdirSync(join(publicDir, "productos"), { recursive: true });

const db = new DatabaseSync(dbPath);

db.exec(`
  CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    brand TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    image TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 999999
  );

  CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer TEXT NOT NULL,
    created_at TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_code TEXT NOT NULL,
    product_name TEXT NOT NULL,
    unit_price INTEGER NOT NULL DEFAULT 0,
    quantity INTEGER NOT NULL,
    FOREIGN KEY(order_id) REFERENCES orders(id)
  );
`);

const productColumns = db.prepare("PRAGMA table_info(products)").all().map((column) => column.name);
if (!productColumns.includes("sort_order")) {
  db.exec("ALTER TABLE products ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 999999");
}
if (!productColumns.includes("price")) {
  db.exec("ALTER TABLE products ADD COLUMN price INTEGER NOT NULL DEFAULT 0");
}

const orderItemColumns = db.prepare("PRAGMA table_info(order_items)").all().map((column) => column.name);
if (!orderItemColumns.includes("unit_price")) {
  db.exec("ALTER TABLE order_items ADD COLUMN unit_price INTEGER NOT NULL DEFAULT 0");
}

const countProducts = db.prepare("SELECT COUNT(*) AS total FROM products").get().total;
if (countProducts === 0) {
  const seed = db.prepare(`
    INSERT INTO products (code, name, brand, category, image, price)
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  const seedProducts = [
    {
      code: "PEND-001",
      name: "Producto pendiente de catalogar",
      brand: "Red de Marcas",
      category: "Catalogo",
      image: "/productos/placeholder.svg",
      price: 0
    }
  ];
  db.exec("BEGIN");
  try {
    for (const item of seedProducts) {
      seed.run(item.code, item.name, item.brand, item.category, item.image, item.price);
    }
    db.exec("COMMIT");
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}

function runTransaction(work) {
  db.exec("BEGIN");
  try {
    const result = work();
    db.exec("COMMIT");
    return result;
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon"
};

function json(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(body));
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString("utf8");
  return raw ? JSON.parse(raw) : {};
}

function normalizeProduct(product) {
  return {
    code: String(product.code ?? "").trim(),
    name: String(product.name ?? "").trim(),
    brand: String(product.brand ?? "").trim(),
    category: String(product.category ?? "").trim(),
    image: String(product.image ?? "").trim(),
    price: Number(product.price ?? product.precio ?? 0) || 0
  };
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function csvEscape(value) {
  const text = String(value ?? "");
  return `"${text.replaceAll('"', '""')}"`;
}

function sendCsv(res, rows, date) {
  const header = ["Fecha", "Cliente/Tienda", "Codigo", "Producto", "Cantidad", "Precio unitario", "Total"];
  const lines = [
    header.map(csvEscape).join(","),
    ...rows.map((row) =>
      [
        row.created_at,
        row.customer,
        row.product_code,
        row.product_name,
        row.quantity,
        row.unit_price,
        row.quantity * row.unit_price
      ].map(csvEscape).join(",")
    )
  ];
  const fileName = `informe-pedidos-${date}.csv`;
  res.writeHead(200, {
    "Content-Type": "text/csv; charset=utf-8",
    "Content-Disposition": `attachment; filename="${fileName}"`
  });
  res.end(`\uFEFF${lines.join("\n")}`);
}

function buildDailySummary(date) {
  const rows = db
    .prepare(`
      SELECT
        o.customer,
        i.product_code,
        i.product_name,
        i.unit_price,
        SUM(i.quantity) AS quantity,
        SUM(i.quantity * i.unit_price) AS total
      FROM orders o
      JOIN order_items i ON i.order_id = o.id
      WHERE substr(o.created_at, 1, 10) = ?
      GROUP BY o.customer, i.product_code, i.product_name, i.unit_price
      ORDER BY o.customer, i.product_name, i.product_code
    `)
    .all(date);

  const orderCounts = db
    .prepare(`
      SELECT customer, COUNT(*) AS orders
      FROM orders
      WHERE substr(created_at, 1, 10) = ?
      GROUP BY customer
    `)
    .all(date);

  const countsByCustomer = new Map(orderCounts.map((row) => [row.customer, row.orders]));
  const storesByName = new Map();

  for (const row of rows) {
    if (!storesByName.has(row.customer)) {
      storesByName.set(row.customer, {
        customer: row.customer,
        orderCount: countsByCustomer.get(row.customer) || 0,
        total: 0,
        items: []
      });
    }

    const store = storesByName.get(row.customer);
    const total = Number(row.total || 0);
    store.total += total;
    store.items.push({
      code: row.product_code,
      name: row.product_name,
      quantity: Number(row.quantity || 0),
      unitPrice: Number(row.unit_price || 0),
      total
    });
  }

  const stores = Array.from(storesByName.values());
  return {
    date,
    storeCount: stores.length,
    grandTotal: stores.reduce((sum, store) => sum + store.total, 0),
    stores
  };
}

async function handleApi(req, res, url) {
  if (req.method === "GET" && url.pathname === "/api/products") {
    const products = db
      .prepare("SELECT code, name, brand, category, image, price FROM products ORDER BY brand, sort_order, name, code")
      .all();
    json(res, 200, products);
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/products/bulk") {
    const body = await readBody(req);
    const products = Array.isArray(body.products) ? body.products.map(normalizeProduct) : [];
    const valid = products.filter((product) => product.code && product.name);

    if (valid.length === 0) {
      json(res, 400, { message: "No hay productos validos para importar." });
      return;
    }

    const upsert = db.prepare(`
      INSERT INTO products (code, name, brand, category, image, price, sort_order)
      VALUES (?, ?, ?, ?, ?, ?, 999999)
      ON CONFLICT(code) DO UPDATE SET
        name = excluded.name,
        brand = excluded.brand,
        category = excluded.category,
        image = excluded.image,
        price = excluded.price,
        sort_order = excluded.sort_order
    `);

    runTransaction(() => {
      for (const product of valid) {
        upsert.run(product.code, product.name, product.brand, product.category, product.image || "/productos/placeholder.svg", product.price);
      }
    });

    json(res, 200, { imported: valid.length });
    return;
  }

  if (req.method === "PATCH" && url.pathname.startsWith("/api/products/")) {
    const currentCode = decodeURIComponent(url.pathname.replace("/api/products/", "")).trim();
    const body = await readBody(req);
    const nextCode = String(body.code ?? body.newCode ?? currentCode).trim();
    const nextPrice = Number(body.price ?? body.precio ?? 0);

    if (!currentCode || !nextCode) {
      json(res, 400, { message: "El codigo actual y el nuevo codigo son obligatorios." });
      return;
    }

    if (!Number.isInteger(nextPrice) || nextPrice < 0) {
      json(res, 400, { message: "El precio debe ser un numero entero mayor o igual a cero." });
      return;
    }

    const product = db.prepare("SELECT code FROM products WHERE code = ?").get(currentCode);
    if (!product) {
      json(res, 404, { message: "Producto no encontrado." });
      return;
    }

    const duplicate = db.prepare("SELECT code FROM products WHERE code = ? AND code <> ?").get(nextCode, currentCode);
    if (duplicate) {
      json(res, 409, { message: `Ya existe un producto con el codigo ${nextCode}.` });
      return;
    }

    db.prepare("UPDATE products SET code = ?, price = ? WHERE code = ?").run(nextCode, nextPrice, currentCode);
    const updated = db
      .prepare("SELECT code, name, brand, category, image, price FROM products WHERE code = ?")
      .get(nextCode);
    json(res, 200, updated);
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/orders") {
    const body = await readBody(req);
    const customer = String(body.customer ?? "").trim();
    const items = Array.isArray(body.items) ? body.items : [];

    if (!customer) {
      json(res, 400, { message: "El cliente o tienda es obligatorio." });
      return;
    }

    const validItems = items
      .map((item) => ({
        code: String(item.code ?? "").trim(),
        name: String(item.name ?? "").trim(),
        price: Number(item.price ?? 0) || 0,
        quantity: Number(item.quantity)
      }))
      .filter((item) => item.code && item.name && Number.isInteger(item.quantity) && item.quantity > 0);

    if (validItems.length === 0) {
      json(res, 400, { message: "Agrega al menos un producto al pedido." });
      return;
    }

    const createdAt = new Date().toISOString();
    const orderId = runTransaction(() => {
      const order = db.prepare("INSERT INTO orders (customer, created_at) VALUES (?, ?)").run(customer, createdAt);
      const itemStmt = db.prepare(`
        INSERT INTO order_items (order_id, product_code, product_name, unit_price, quantity)
        VALUES (?, ?, ?, ?, ?)
      `);
      for (const item of validItems) {
        const product = db.prepare("SELECT price FROM products WHERE code = ?").get(item.code);
        const unitPrice = Number(product?.price ?? item.price ?? 0) || 0;
        itemStmt.run(order.lastInsertRowid, item.code, item.name, unitPrice, item.quantity);
      }
      return order.lastInsertRowid;
    });

    json(res, 201, { id: orderId, createdAt });
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/orders/today") {
    const date = url.searchParams.get("date") || todayISO();
    const rows = db
      .prepare(`
        SELECT o.id, o.customer, o.created_at, i.product_code, i.product_name, i.unit_price, i.quantity
        FROM orders o
        JOIN order_items i ON i.order_id = o.id
        WHERE substr(o.created_at, 1, 10) = ?
        ORDER BY o.created_at DESC, o.customer, i.product_name
      `)
      .all(date);
    json(res, 200, rows);
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/orders/summary") {
    const date = url.searchParams.get("date") || todayISO();
    json(res, 200, buildDailySummary(date));
    return;
  }

  if (req.method === "DELETE" && url.pathname === "/api/orders") {
    const date = url.searchParams.get("date");
    if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      json(res, 400, { message: "La fecha es obligatoria en formato YYYY-MM-DD." });
      return;
    }

    const body = await readBody(req);
    const pin = String(body.pin ?? "").trim();
    if (!/^\d{4}$/.test(pin) || pin !== deletePin) {
      json(res, 403, { message: "Clave de eliminacion incorrecta." });
      return;
    }

    const result = runTransaction(() => {
      const orderIds = db
        .prepare("SELECT id FROM orders WHERE substr(created_at, 1, 10) = ?")
        .all(date)
        .map((row) => row.id);

      let deletedItems = 0;
      for (const orderId of orderIds) {
        deletedItems += db.prepare("DELETE FROM order_items WHERE order_id = ?").run(orderId).changes;
      }
      const deletedOrders = db.prepare("DELETE FROM orders WHERE substr(created_at, 1, 10) = ?").run(date).changes;
      return { date, deletedOrders, deletedItems };
    });

    json(res, 200, result);
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/report") {
    const date = url.searchParams.get("date") || todayISO();
    const rows = db
      .prepare(`
        SELECT o.customer, o.created_at, i.product_code, i.product_name, i.unit_price, i.quantity
        FROM orders o
        JOIN order_items i ON i.order_id = o.id
        WHERE substr(o.created_at, 1, 10) = ?
        ORDER BY o.customer, i.product_name
      `)
      .all(date);
    sendCsv(res, rows, date);
    return;
  }

  json(res, 404, { message: "Ruta no encontrada." });
}

function serveStatic(req, res, url) {
  if (url.pathname.startsWith("/productos/")) {
    const productAsset = resolve(join(publicDir, decodeURIComponent(url.pathname)));
    const productBase = resolve(join(publicDir, "productos"));

    if (!productAsset.startsWith(productBase) || !existsSync(productAsset)) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("Producto no encontrado");
      return;
    }

    const ext = extname(productAsset).toLowerCase();
    res.writeHead(200, { "Content-Type": mimeTypes[ext] || "application/octet-stream" });
    res.end(readFileSync(productAsset));
    return;
  }

  const baseDir = existsSync(distDir) ? distDir : publicDir;
  const requested = url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname);
  const filePath = resolve(join(baseDir, requested));
  const safeBase = resolve(baseDir);

  if (!filePath.startsWith(safeBase)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  if (!existsSync(filePath)) {
    const fallback = join(baseDir, "index.html");
    if (existsSync(fallback)) {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(readFileSync(fallback));
      return;
    }
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("Ejecuta primero: npm.cmd run build");
    return;
  }

  const ext = extname(filePath).toLowerCase();
  res.writeHead(200, { "Content-Type": mimeTypes[ext] || "application/octet-stream" });
  res.end(readFileSync(filePath));
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", "http://localhost");
    if (url.pathname.startsWith("/api/")) {
      await handleApi(req, res, url);
      return;
    }
    serveStatic(req, res, url);
  } catch (error) {
    console.error(error);
    json(res, 500, { message: "Error interno del servidor." });
  }
});

const port = Number(process.env.PORT || 3000);
server.listen(port, "0.0.0.0", () => {
  console.log(`Catalogo Red de Marcas listo en http://localhost:${port}`);
});
