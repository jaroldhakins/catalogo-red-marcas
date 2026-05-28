import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Check,
  ClipboardList,
  Download,
  FileUp,
  Minus,
  PackageSearch,
  Pencil,
  Plus,
  Search,
  Save,
  Store,
  Trash2,
  X
} from "lucide-react";
import {
  createProduct,
  deleteProduct,
  deleteOrdersForDate as deleteOrdersForDateFromStore,
  getDailySummary,
  getProducts,
  importProducts,
  isSupabaseMode,
  saveOrder as saveOrderToStore,
  updateProduct,
  type DailySummary,
  type Product
} from "./dataClient";
import "./styles.css";

type Cart = Record<string, number>;

type BrandSummary = {
  name: string;
  count: number;
};

type PromoCategory = "Promos" | "Novedades";

const today = new Date().toISOString().slice(0, 10);

function parseCsv(text: string): Product[] {
  const lines = text.trim().split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];

  const parseLine = (line: string) => {
    const values: string[] = [];
    let current = "";
    let quoted = false;

    for (let index = 0; index < line.length; index += 1) {
      const char = line[index];
      const next = line[index + 1];

      if (char === '"' && quoted && next === '"') {
        current += '"';
        index += 1;
      } else if (char === '"') {
        quoted = !quoted;
      } else if (char === "," && !quoted) {
        values.push(current.trim());
        current = "";
      } else {
        current += char;
      }
    }

    values.push(current.trim());
    return values;
  };

  const headers = parseLine(lines[0]).map((header) => header.trim().toLowerCase());
  const index = (name: string) => headers.indexOf(name);
  const codeIndex = index("codigo");
  const nameIndex = index("nombre");
  const brandIndex = index("marca");
  const categoryIndex = index("categoria");
  const imageIndex = index("imagen");

  return lines.slice(1).map((line) => {
    const values = parseLine(line);
    return {
      code: values[codeIndex] || "",
      name: values[nameIndex] || "",
      brand: values[brandIndex] || "",
      category: values[categoryIndex] || "",
      image: values[imageIndex] || "/productos/placeholder.svg",
      price: Number(values[headers.indexOf("precio")] || values[headers.indexOf("price")] || 0) || 0
    };
  });
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0
  }).format(value || 0);
}

function csvEscape(value: unknown) {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

function downloadDailyCsv(summary: DailySummary | null) {
  if (!summary) return;
  const rows = [
    ["Fecha", "Cliente/Tienda", "Codigo", "Producto", "Cantidad", "Precio unitario", "Total"],
    ...summary.stores.flatMap((store) =>
      store.items.map((item) => [
        summary.date,
        store.customer,
        item.code,
        item.name,
        item.quantity,
        item.unitPrice,
        item.total
      ])
    )
  ];
  const csv = `\uFEFF${rows.map((row) => row.map(csvEscape).join(",")).join("\n")}`;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `informe-pedidos-${summary.date}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [customerDraft, setCustomerDraft] = useState("");
  const [customer, setCustomer] = useState("");
  const [reportsOnly, setReportsOnly] = useState(false);
  const [cart, setCart] = useState<Cart>({});
  const [query, setQuery] = useState("");
  const [brand, setBrand] = useState("Todas");
  const [category, setCategory] = useState("Todas");
  const [reportDate, setReportDate] = useState(today);
  const [dailySummary, setDailySummary] = useState<DailySummary | null>(null);
  const [sideView, setSideView] = useState<"order" | "reports">("order");
  const [status, setStatus] = useState("");
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [editCode, setEditCode] = useState("");
  const [editPrice, setEditPrice] = useState("");
  const [isCreatingProduct, setIsCreatingProduct] = useState(false);
  const [newProductCategory, setNewProductCategory] = useState<PromoCategory>("Promos");
  const [newProductCode, setNewProductCode] = useState("");
  const [newProductName, setNewProductName] = useState("");
  const [newProductPrice, setNewProductPrice] = useState("");

  async function loadProducts() {
    try {
      const loadedProducts = await getProducts();
      setProducts(loadedProducts);
      if (loadedProducts.length === 0) {
        setStatus("No se encontraron productos en Supabase.");
      }
    } catch (error) {
      setStatus(error instanceof Error ? `No se pudo cargar el catalogo: ${error.message}` : "No se pudo cargar el catalogo.");
    }
  }

  async function loadDailySummary(date = reportDate) {
    try {
      setDailySummary(await getDailySummary(date));
    } catch (error) {
      setStatus(error instanceof Error ? `No se pudo cargar el informe: ${error.message}` : "No se pudo cargar el informe.");
    }
  }

  useEffect(() => {
    loadProducts();
    loadDailySummary(today);
  }, []);

  const brands = useMemo(
    () => ["Todas", ...Array.from(new Set(products.map((product) => product.brand).filter(Boolean))).sort()],
    [products]
  );

  const brandSummaries = useMemo<BrandSummary[]>(() => {
    const counts = new Map<string, number>();
    for (const product of products) {
      const productBrand = product.brand || "Sin marca";
      counts.set(productBrand, (counts.get(productBrand) || 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  }, [products]);

  const categories = useMemo(
    () => ["Todas", ...Array.from(new Set(products.map((product) => product.category).filter(Boolean))).sort()],
    [products]
  );

  const filteredProducts = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return products.filter((product) => {
      const matchesQuery =
        !normalizedQuery ||
        product.name.toLowerCase().includes(normalizedQuery) ||
        product.code.toLowerCase().includes(normalizedQuery);
      const matchesBrand = brand === "Todas" || product.brand === brand;
      const matchesCategory = category === "Todas" || product.category === category;
      return matchesQuery && matchesBrand && matchesCategory;
    });
  }, [brand, category, products, query]);

  const selectedItems = useMemo(
    () =>
      Object.entries(cart)
        .map(([code, quantity]) => {
          const product = products.find((item) => item.code === code);
          return product ? { ...product, quantity } : null;
        })
        .filter(Boolean) as Array<Product & { quantity: number }>,
    [cart, products]
  );

  const totalUnits = selectedItems.reduce((sum, item) => sum + item.quantity, 0);
  const totalValue = selectedItems.reduce((sum, item) => sum + item.quantity * item.price, 0);

  function setQuantity(code: string, quantity: number) {
    setCart((current) => {
      const next = { ...current };
      if (quantity <= 0) delete next[code];
      else next[code] = quantity;
      return next;
    });
  }

  function openEditor(product: Product) {
    setEditingProduct(product);
    setEditCode(product.code);
    setEditPrice(String(product.price || 0));
  }

  async function saveProductEdit(event: React.FormEvent) {
    event.preventDefault();
    if (!editingProduct) return;

    const nextCode = editCode.trim();
    const nextPrice = Number(editPrice);
    let result: Product;
    try {
      result = await updateProduct(editingProduct.code, { code: nextCode, price: nextPrice });
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "No se pudo actualizar el producto.");
      return;
    }

    setProducts((current) =>
      current.map((product) => (product.code === editingProduct.code ? result : product))
    );
    setCart((current) => {
      if (editingProduct.code === result.code || current[editingProduct.code] === undefined) return current;
      const next = { ...current };
      next[result.code] = (next[result.code] || 0) + next[editingProduct.code];
      delete next[editingProduct.code];
      return next;
    });
    setEditingProduct(null);
    setStatus("Producto actualizado correctamente.");
  }

  async function removeEditingProduct() {
    if (!editingProduct) return;
    const confirmed = window.confirm(`Eliminar ${editingProduct.name} del catalogo?`);
    if (!confirmed) return;
    const pin = window.prompt("Ingresa la clave de 4 digitos para eliminar el producto.");
    if (pin === null) return;

    try {
      await deleteProduct(editingProduct.code, pin);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "No se pudo eliminar el producto.");
      return;
    }

    setProducts((current) => current.filter((product) => product.code !== editingProduct.code));
    setCart((current) => {
      const next = { ...current };
      delete next[editingProduct.code];
      return next;
    });
    setEditingProduct(null);
    setStatus("Producto eliminado del catalogo.");
  }

  async function saveNewProduct(event: React.FormEvent) {
    event.preventDefault();
    const code = newProductCode.trim();
    const name = newProductName.trim();
    const price = Number(newProductPrice);

    if (!code || !name) {
      setStatus("El codigo y el nombre son obligatorios.");
      return;
    }

    if (!Number.isInteger(price) || price < 0) {
      setStatus("El precio debe ser un numero entero mayor o igual a cero.");
      return;
    }

    let created: Product;
    try {
      created = await createProduct({
        code,
        name,
        brand: newProductCategory,
        category: newProductCategory,
        image: "/productos/placeholder.svg",
        price
      });
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "No se pudo crear el producto.");
      return;
    }

    setProducts((current) => [...current.filter((product) => product.code !== created.code), created]);
    setBrand(newProductCategory);
    setCategory(newProductCategory);
    setIsCreatingProduct(false);
    setNewProductCode("");
    setNewProductName("");
    setNewProductPrice("");
    setStatus(`${newProductCategory.slice(0, -1)} agregada correctamente.`);
  }

  async function saveOrder() {
    setStatus("");
    try {
      await saveOrderToStore(
        customer,
        selectedItems.map((item) => ({
          code: item.code,
          name: item.name,
          price: item.price,
          quantity: item.quantity
        }))
      );
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "No se pudo guardar el pedido.");
      return;
    }

    setCart({});
    setStatus("Pedido guardado correctamente.");
    await loadDailySummary();
  }

  async function deleteOrdersForDate() {
    const confirmed = window.confirm(`Eliminar todos los pedidos del ${reportDate}? Esta accion no se puede deshacer.`);
    if (!confirmed) return;
    const pin = window.prompt("Ingresa la clave de 4 digitos para eliminar pedidos.");
    if (pin === null) return;

    let result: { deletedOrders: number; deletedItems: number };
    try {
      result = await deleteOrdersForDateFromStore(reportDate, pin);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "No se pudieron eliminar los pedidos.");
      return;
    }

    setStatus(`Pedidos eliminados: ${result.deletedOrders}. Lineas eliminadas: ${result.deletedItems}.`);
    await loadDailySummary();
  }

  async function importCatalog(file: File) {
    const text = await file.text();
    const parsedProducts = parseCsv(text);
    try {
      const imported = await importProducts(parsedProducts);
      setStatus(`Catalogo actualizado: ${imported} productos.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "No se pudo importar el catalogo.");
      return;
    }
    await loadProducts();
  }

  function renderDailyReport() {
    return (
      <div className="daily-report detailed-report">
        <div className="report-toolbar">
          <div>
            <h3>Informe por tienda</h3>
            <span>{dailySummary?.storeCount || 0} tiendas - {formatCurrency(dailySummary?.grandTotal || 0)}</span>
          </div>
          <input
            type="date"
            value={reportDate}
            onChange={async (event) => {
              setReportDate(event.target.value);
              await loadDailySummary(event.target.value);
            }}
          />
        </div>

        <div className="report-actions">
          <button className="secondary-button" onClick={() => downloadDailyCsv(dailySummary)}>
            Descargar CSV
          </button>
          <button className="danger-button" onClick={deleteOrdersForDate} disabled={!dailySummary?.stores.length}>
            <Trash2 size={16} />
            Eliminar fecha
          </button>
        </div>

        {dailySummary && dailySummary.stores.length > 0 ? (
          <div className="store-report-list">
            {dailySummary.stores.map((store) => (
              <section className="store-report" key={store.customer}>
                <div className="store-report-heading">
                  <div>
                    <strong>{store.customer}</strong>
                    <span>{store.orderCount} pedidos</span>
                  </div>
                  <b>{formatCurrency(store.total)}</b>
                </div>
                <div className="store-report-items">
                  {store.items.map((item) => (
                    <div className="store-report-item" key={`${store.customer}-${item.code}-${item.unitPrice}`}>
                      <div>
                        <strong>{item.name}</strong>
                        <span>{item.code}</span>
                      </div>
                      <span>{item.quantity}</span>
                      <span>{formatCurrency(item.unitPrice)}</span>
                      <b>{formatCurrency(item.total)}</b>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <p>No hay pedidos para esta fecha.</p>
        )}
      </div>
    );
  }

  if (reportsOnly) {
    return (
      <main className="app-shell reports-shell">
        <header className="topbar">
          <div>
            <span className="eyebrow">{isSupabaseMode() ? "Pedido en nube" : "Pedido local"}</span>
            <h1>Pedidos del dia</h1>
          </div>
          <div className="topbar-actions">
            <button
              className="secondary-button"
              onClick={() => {
                setReportsOnly(false);
                setCustomer("");
              }}
            >
              <Store size={18} />
              Nuevo pedido
            </button>
          </div>
        </header>

        {status && <p className="status">{status}</p>}

        <section className="reports-panel">
          {renderDailyReport()}
        </section>
      </main>
    );
  }

  if (!customer) {
    return (
      <main className="entry-screen">
        <section className="entry-panel">
          <div className="brand-lockup">
            <Store size={30} />
            <div>
              <span>Red de Marcas</span>
              <strong>Catalogo de pedidos</strong>
            </div>
          </div>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (customerDraft.trim()) {
                setReportsOnly(false);
                setCustomer(customerDraft.trim());
              }
            }}
          >
            <label htmlFor="customer">Nombre de tienda o cliente</label>
            <input
              id="customer"
              value={customerDraft}
              onChange={(event) => setCustomerDraft(event.target.value)}
              autoFocus
              placeholder="Ej: Tienda La Esperanza"
            />
            <button type="submit">
              <Check size={18} />
              Iniciar pedido
            </button>
          </form>
          <button
            className="entry-secondary"
            onClick={() => {
              setReportsOnly(true);
              setSideView("reports");
              loadDailySummary(reportDate);
            }}
          >
            <ClipboardList size={18} />
            Ver pedidos del dia
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <span className="eyebrow">{isSupabaseMode() ? "Pedido en nube" : "Pedido local"}</span>
          <h1>{customer}</h1>
        </div>
        <div className="topbar-actions">
          <button className="secondary-button" onClick={() => setIsCreatingProduct(true)}>
            <Plus size={18} />
            Agregar producto
          </button>
          <label className="icon-button" title="Importar catalogo CSV">
            <FileUp size={19} />
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) importCatalog(file);
                event.currentTarget.value = "";
              }}
            />
          </label>
          <a className="icon-button" href={`/api/report?date=${today}`} title="Descargar informe del dia">
            <Download size={19} />
          </a>
          <button className="secondary-button" onClick={() => setCustomer("")}>
            Cambiar cliente
          </button>
        </div>
      </header>

      {status && <p className="status">{status}</p>}

      <section className="workspace">
        <section className="catalog-area">
          <section className="brand-filter-panel">
            <div className="brand-filter-heading">
              <div>
                <span className="eyebrow">Filtrar por marca</span>
                <h2>{brand === "Todas" ? "Todas las marcas" : brand}</h2>
              </div>
              <button className={brand === "Todas" ? "brand-pill active" : "brand-pill"} onClick={() => setBrand("Todas")}>
                Todas
                <span>{products.length}</span>
              </button>
            </div>
            <div className="brand-strip">
              {brandSummaries.map((item) => (
                <button
                  className={brand === item.name ? "brand-tile active" : "brand-tile"}
                  key={item.name}
                  onClick={() => setBrand(item.name)}
                >
                  <strong>{item.name}</strong>
                  <span>{item.count} productos</span>
                </button>
              ))}
            </div>
          </section>

          <div className="toolbar">
            <div className="searchbox">
              <Search size={18} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Buscar producto o codigo"
              />
            </div>
            <select value={brand} onChange={(event) => setBrand(event.target.value)}>
              {brands.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              {categories.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </div>

          <div className="product-grid">
            {filteredProducts.map((product) => {
              const quantity = cart[product.code] || 0;
              return (
                <article className={quantity > 0 ? "product-card selected" : "product-card"} key={product.code}>
                  <button className="image-button" onClick={() => setQuantity(product.code, quantity + 1)}>
                    <img
                      src={product.image || "/productos/placeholder.svg"}
                      alt={product.name}
                      loading="lazy"
                      decoding="async"
                      onError={(event) => {
                        event.currentTarget.src = "/productos/placeholder.svg";
                      }}
                    />
                  </button>
                  <div className="product-info">
                    <span>{product.brand || "Sin marca"}</span>
                    <h2>{product.name}</h2>
                    <p>{product.code}</p>
                    <strong className="price-label">{formatCurrency(product.price)}</strong>
                  </div>
                  <button className="edit-product-button" onClick={() => openEditor(product)} title="Editar codigo y precio">
                    <Pencil size={16} />
                  </button>
                  <div className="quantity-control">
                    <button onClick={() => setQuantity(product.code, quantity - 1)} aria-label="Restar">
                      <Minus size={17} />
                    </button>
                    <strong>{quantity}</strong>
                    <button onClick={() => setQuantity(product.code, quantity + 1)} aria-label="Sumar">
                      <Plus size={17} />
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <aside className="order-panel">
          <div className="side-tabs">
            <button className={sideView === "order" ? "active" : ""} onClick={() => setSideView("order")}>
              Pedido
            </button>
            <button className={sideView === "reports" ? "active" : ""} onClick={() => setSideView("reports")}>
              Pedidos del dia
            </button>
          </div>

          {sideView === "order" ? (
            <>
          <div className="panel-heading">
            <ClipboardList size={20} />
            <div>
              <h2>Pedido actual</h2>
              <span>{totalUnits} unidades - {formatCurrency(totalValue)}</span>
            </div>
          </div>

          <div className="cart-list">
            {selectedItems.length === 0 ? (
              <div className="empty-state">
                <PackageSearch size={34} />
                <p>Selecciona productos del catalogo.</p>
              </div>
            ) : (
              selectedItems.map((item) => (
                <div className="cart-row" key={item.code}>
                  <div>
                    <strong>{item.name}</strong>
                    <span>{item.code} - {formatCurrency(item.price)}</span>
                  </div>
                  <input
                    type="number"
                    min={1}
                    value={item.quantity}
                    onChange={(event) => setQuantity(item.code, Number(event.target.value))}
                  />
                  <button onClick={() => setQuantity(item.code, 0)} aria-label="Quitar">
                    <Trash2 size={16} />
                  </button>
                </div>
              ))
            )}
          </div>

          <button className="primary-action" disabled={selectedItems.length === 0} onClick={saveOrder}>
            <Check size={18} />
            Guardar pedido
          </button>
            </>
          ) : (
            <>

          {renderDailyReport()}
            </>
          )}
        </aside>
      </section>

      {editingProduct && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <form className="edit-modal" onSubmit={saveProductEdit}>
            <div className="edit-modal-heading">
              <div>
                <span className="eyebrow">Edicion manual</span>
                <h2>{editingProduct.name}</h2>
              </div>
              <button type="button" className="icon-button" onClick={() => setEditingProduct(null)} title="Cerrar">
                <X size={18} />
              </button>
            </div>
            <label htmlFor="edit-code">Codigo</label>
            <input id="edit-code" value={editCode} onChange={(event) => setEditCode(event.target.value)} />
            <label htmlFor="edit-price">Precio</label>
            <input
              id="edit-price"
              type="number"
              min={0}
              step={1}
              value={editPrice}
              onChange={(event) => setEditPrice(event.target.value)}
            />
            <button type="submit">
              <Save size={18} />
              Guardar cambios
            </button>
            <button type="button" className="danger-button" onClick={removeEditingProduct}>
              <Trash2 size={18} />
              Eliminar producto
            </button>
          </form>
        </div>
      )}

      {isCreatingProduct && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <form className="edit-modal" onSubmit={saveNewProduct}>
            <div className="edit-modal-heading">
              <div>
                <span className="eyebrow">Promos y novedades</span>
                <h2>Agregar producto</h2>
              </div>
              <button type="button" className="icon-button" onClick={() => setIsCreatingProduct(false)} title="Cerrar">
                <X size={18} />
              </button>
            </div>
            <label htmlFor="new-product-category">Categoria</label>
            <select
              id="new-product-category"
              value={newProductCategory}
              onChange={(event) => setNewProductCategory(event.target.value as PromoCategory)}
            >
              <option>Promos</option>
              <option>Novedades</option>
            </select>
            <label htmlFor="new-product-code">Codigo</label>
            <input
              id="new-product-code"
              value={newProductCode}
              onChange={(event) => setNewProductCode(event.target.value)}
              autoFocus
            />
            <label htmlFor="new-product-name">Nombre</label>
            <input
              id="new-product-name"
              value={newProductName}
              onChange={(event) => setNewProductName(event.target.value)}
            />
            <label htmlFor="new-product-price">Precio</label>
            <input
              id="new-product-price"
              type="number"
              min={0}
              step={1}
              value={newProductPrice}
              onChange={(event) => setNewProductPrice(event.target.value)}
            />
            <button type="submit">
              <Save size={18} />
              Guardar producto
            </button>
          </form>
        </div>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
