import { createClient } from "@supabase/supabase-js";

export type Product = {
  code: string;
  name: string;
  brand: string;
  category: string;
  image: string;
  price: number;
};

export type OrderItemInput = {
  code: string;
  name: string;
  price: number;
  quantity: number;
};

export type StoreReportItem = {
  code: string;
  name: string;
  quantity: number;
  unitPrice: number;
  total: number;
};

export type StoreReport = {
  customer: string;
  orderCount: number;
  total: number;
  items: StoreReportItem[];
};

export type DailySummary = {
  date: string;
  storeCount: number;
  grandTotal: number;
  stores: StoreReport[];
};

const fallbackSupabaseUrl = "https://swnmnwggvbvqthdnfjka.supabase.co";
const fallbackSupabaseKey = "sb_publishable_hwsIHmt3qAxeduoDQ-x5yA_UNQI2xjg";
const deletedCategory = "Eliminados";

function cleanEnvValue(value: string | undefined, fallback: string) {
  const cleaned = String(value || "")
    .split(/\r?\n/)
    .map((line) => line.replace(/^value:\s*/i, "").trim())
    .filter(Boolean)
    .at(-1);
  return cleaned || fallback;
}

const supabaseUrl = cleanEnvValue(import.meta.env.VITE_SUPABASE_URL as string | undefined, fallbackSupabaseUrl);
const supabaseKey = cleanEnvValue(import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined, fallbackSupabaseKey);
const supabase = supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey) : null;

function nextDate(date: string) {
  const parsed = new Date(`${date}T00:00:00.000Z`);
  parsed.setUTCDate(parsed.getUTCDate() + 1);
  return parsed.toISOString().slice(0, 10);
}

function bogotaRange(date: string) {
  return {
    start: `${date}T05:00:00.000Z`,
    end: `${nextDate(date)}T05:00:00.000Z`
  };
}

function mapProduct(row: Record<string, unknown>): Product {
  return {
    code: String(row.code ?? ""),
    name: String(row.name ?? ""),
    brand: String(row.brand ?? ""),
    category: String(row.category ?? ""),
    image: String(row.image ?? ""),
    price: Number(row.price ?? 0)
  };
}

export function isSupabaseMode() {
  return Boolean(supabase);
}

export async function getProducts(): Promise<Product[]> {
  if (!supabase) {
    const response = await fetch("/api/products");
    return response.json();
  }

  const { data, error } = await supabase
    .from("products")
    .select("code,name,brand,category,image,price,sort_order")
    .order("brand", { ascending: true })
    .order("sort_order", { ascending: true })
    .order("name", { ascending: true });

  if (error) throw error;
  return (data || []).map(mapProduct).filter((product) => product.category !== deletedCategory);
}

export async function updateProduct(currentCode: string, product: Pick<Product, "code" | "price">): Promise<Product> {
  if (!supabase) {
    const response = await fetch(`/api/products/${encodeURIComponent(currentCode)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(product)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "No se pudo actualizar el producto.");
    return result;
  }

  const { data, error } = await supabase
    .from("products")
    .update({ code: product.code, price: product.price })
    .eq("code", currentCode)
    .select("code,name,brand,category,image,price")
    .single();

  if (error) throw error;
  return mapProduct(data);
}

export async function createProduct(product: Product): Promise<Product> {
  if (!supabase) {
    const response = await fetch("/api/products", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(product)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "No se pudo crear el producto.");
    return result;
  }

  const { data, error } = await supabase
    .from("products")
    .insert({
      code: product.code,
      name: product.name,
      brand: product.brand,
      category: product.category,
      image: product.image || "/productos/placeholder.svg",
      price: product.price,
      sort_order: 999999
    })
    .select("code,name,brand,category,image,price")
    .single();

  if (error) throw error;
  return mapProduct(data);
}

export async function deleteProduct(code: string, pin: string) {
  if (pin !== "0000") throw new Error("Clave de eliminacion incorrecta.");

  if (!supabase) {
    const response = await fetch(`/api/products/${encodeURIComponent(code)}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "No se pudo eliminar el producto.");
    return result as { deletedProducts: number };
  }

  const deletedCode = `ELIMINADO-${Date.now()}-${code}`;
  const { error, count } = await supabase
    .from("products")
    .update({
      code: deletedCode,
      name: `Producto eliminado ${code}`,
      brand: deletedCategory,
      category: deletedCategory,
      image: "/productos/placeholder.svg",
      price: 0,
      sort_order: 999999
    }, { count: "exact" })
    .eq("code", code);

  if (error) throw error;
  return { deletedProducts: count || 0 };
}

export async function importProducts(products: Product[]) {
  if (!supabase) {
    const response = await fetch("/api/products/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ products })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "No se pudo importar el catalogo.");
    return result.imported as number;
  }

  const { error } = await supabase.from("products").upsert(
    products.map((product) => ({
      code: product.code,
      name: product.name,
      brand: product.brand,
      category: product.category,
      image: product.image,
      price: product.price,
      sort_order: 999999
    })),
    { onConflict: "code" }
  );

  if (error) throw error;
  return products.length;
}

export async function saveOrder(customer: string, items: OrderItemInput[]) {
  if (!supabase) {
    const response = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ customer, items })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "No se pudo guardar el pedido.");
    return result;
  }

  const { data: order, error: orderError } = await supabase
    .from("orders")
    .insert({ customer })
    .select("id,created_at")
    .single();

  if (orderError) throw orderError;

  const { error: itemError } = await supabase.from("order_items").insert(
    items.map((item) => ({
      order_id: order.id,
      product_code: item.code,
      product_name: item.name,
      unit_price: item.price,
      quantity: item.quantity
    }))
  );

  if (itemError) throw itemError;
  return order;
}

export async function getDailySummary(date: string): Promise<DailySummary> {
  if (!supabase) {
    const response = await fetch(`/api/orders/summary?date=${date}`);
    return response.json();
  }

  const range = bogotaRange(date);
  const { data: orders, error } = await supabase
    .from("orders")
    .select("id,customer,created_at,order_items(product_code,product_name,unit_price,quantity)")
    .gte("created_at", range.start)
    .lt("created_at", range.end)
    .order("customer", { ascending: true });

  if (error) throw error;

  const storesByName = new Map<string, StoreReport>();
  for (const order of orders || []) {
    const customer = String(order.customer);
    if (!storesByName.has(customer)) {
      storesByName.set(customer, { customer, orderCount: 0, total: 0, items: [] });
    }

    const store = storesByName.get(customer)!;
    store.orderCount += 1;
    const items = Array.isArray(order.order_items) ? order.order_items : [];
    for (const item of items) {
      const code = String(item.product_code);
      const unitPrice = Number(item.unit_price || 0);
      const quantity = Number(item.quantity || 0);
      const total = unitPrice * quantity;
      const existing = store.items.find((row) => row.code === code && row.unitPrice === unitPrice);
      if (existing) {
        existing.quantity += quantity;
        existing.total += total;
      } else {
        store.items.push({
          code,
          name: String(item.product_name),
          unitPrice,
          quantity,
          total
        });
      }
      store.total += total;
    }
  }

  const stores = Array.from(storesByName.values()).map((store) => ({
    ...store,
    items: store.items.sort((a, b) => a.name.localeCompare(b.name))
  }));

  return {
    date,
    storeCount: stores.length,
    grandTotal: stores.reduce((sum, store) => sum + store.total, 0),
    stores
  };
}

export async function deleteOrdersForDate(date: string, pin: string) {
  if (!supabase) {
    const response = await fetch(`/api/orders?date=${date}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "No se pudieron eliminar los pedidos.");
    return result as { deletedOrders: number; deletedItems: number };
  }

  const { data, error } = await supabase.rpc("delete_orders_by_date", {
    target_date: date,
    provided_pin: pin
  });

  if (error) throw error;
  const result = Array.isArray(data) ? data[0] : data;
  return {
    deletedOrders: Number(result?.deleted_orders || 0),
    deletedItems: Number(result?.deleted_items || 0)
  };
}
