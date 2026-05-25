# Despliegue en Supabase + Vercel

## 1. Crear proyecto en Supabase

1. Entra a `https://supabase.com`.
2. Crea una cuenta o inicia sesion.
3. Crea un proyecto nuevo.
4. Guarda estos datos:
   - Project URL
   - anon public key

Estan en:

```text
Project Settings > API
```

## 2. Crear tablas y funcion de borrado

1. En Supabase abre `SQL Editor`.
2. Crea un nuevo query.
3. Pega todo el contenido de:

```text
supabase/schema.sql
```

4. Ejecuta el query.

La clave para borrar pedidos queda por defecto en `0000`.

## 3. Cargar productos

1. En Supabase abre otro query en `SQL Editor`.
2. Pega todo el contenido de:

```text
supabase/seed_products.sql
```

3. Ejecuta el query.

Debe cargar 535 productos.

## 4. Probar localmente contra Supabase

1. Crea un archivo `.env` en la raiz del proyecto.
2. Copia el contenido de `.env.example`.
3. Reemplaza:

```text
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
```

4. Ejecuta:

```powershell
npm.cmd run build
```

Si esas variables existen, la app usa Supabase. Si no existen, usa el servidor local SQLite.

## 5. Subir a GitHub

Vercel funciona mejor conectando el proyecto desde GitHub.

1. Crea un repositorio en GitHub.
2. Sube este proyecto.
3. No subas `.env`.

## 6. Desplegar en Vercel

1. Entra a `https://vercel.com`.
2. Crea cuenta o inicia sesion.
3. Click en `Add New Project`.
4. Importa el repo de GitHub.
5. Framework: Vite.
6. Build command:

```text
npm run build
```

7. Output directory:

```text
dist
```

8. En `Environment Variables` agrega:

```text
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
```

9. Deploy.

## 7. Usar en Android

1. Abre la URL de Vercel en Chrome Android.
2. Menu de tres puntos.
3. `Agregar a pantalla principal`.

La app queda como acceso directo y los pedidos se guardan en Supabase.
