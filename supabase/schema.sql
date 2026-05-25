create extension if not exists pgcrypto;

create table if not exists public.products (
  code text primary key,
  name text not null,
  brand text not null default '',
  category text not null default '',
  image text not null default '',
  price integer not null default 0 check (price >= 0),
  sort_order integer not null default 999999,
  updated_at timestamptz not null default now()
);

create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  customer text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  product_code text not null,
  product_name text not null,
  unit_price integer not null default 0 check (unit_price >= 0),
  quantity integer not null check (quantity > 0)
);

create index if not exists orders_created_at_idx on public.orders(created_at);
create index if not exists orders_customer_idx on public.orders(customer);
create index if not exists order_items_order_id_idx on public.order_items(order_id);
create index if not exists products_brand_sort_idx on public.products(brand, sort_order);

alter table public.products enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;

drop policy if exists "public read products" on public.products;
create policy "public read products"
  on public.products for select
  to anon
  using (true);

drop policy if exists "public update products" on public.products;
create policy "public update products"
  on public.products for update
  to anon
  using (true)
  with check (true);

drop policy if exists "public insert products" on public.products;
create policy "public insert products"
  on public.products for insert
  to anon
  with check (true);

drop policy if exists "public read orders" on public.orders;
create policy "public read orders"
  on public.orders for select
  to anon
  using (true);

drop policy if exists "public insert orders" on public.orders;
create policy "public insert orders"
  on public.orders for insert
  to anon
  with check (true);

drop policy if exists "public read order items" on public.order_items;
create policy "public read order items"
  on public.order_items for select
  to anon
  using (true);

drop policy if exists "public insert order items" on public.order_items;
create policy "public insert order items"
  on public.order_items for insert
  to anon
  with check (true);

create or replace function public.delete_orders_by_date(target_date text, provided_pin text)
returns table(deleted_orders integer, deleted_items integer)
language plpgsql
security definer
set search_path = public
as $$
declare
  expected_pin text := coalesce(current_setting('app.delete_pin', true), '0000');
  start_at timestamptz;
  end_at timestamptz;
  order_ids uuid[];
begin
  if provided_pin is null or provided_pin !~ '^[0-9]{4}$' or provided_pin <> expected_pin then
    raise exception 'Clave de eliminacion incorrecta';
  end if;

  start_at := (target_date::date::timestamp at time zone 'America/Bogota');
  end_at := ((target_date::date + 1)::timestamp at time zone 'America/Bogota');

  select coalesce(array_agg(id), '{}') into order_ids
  from public.orders
  where created_at >= start_at and created_at < end_at;

  select count(*)::integer into deleted_items
  from public.order_items
  where order_id = any(order_ids);

  delete from public.orders
  where id = any(order_ids);

  deleted_orders := coalesce(array_length(order_ids, 1), 0);
  return next;
end;
$$;

grant execute on function public.delete_orders_by_date(text, text) to anon;
