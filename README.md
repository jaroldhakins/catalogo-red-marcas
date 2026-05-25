# Catalogo Red de Marcas

App local para tomar pedidos por tienda o cliente desde un catalogo interactivo.

Para despliegue en nube con Supabase + Vercel revisa:

```text
DEPLOY_SUPABASE_VERCEL.md
```

## Uso rapido

1. Compilar la app:

```powershell
npm.cmd run build
```

2. Iniciar el servidor local:

```powershell
npm.cmd run start
```

3. Abrir en el computador:

```text
http://localhost:3000
```

Para usarla desde Android en la misma red Wi-Fi, abre la IP del computador con el puerto `3000`, por ejemplo:

```text
http://192.168.1.25:3000
```

## Catalogo

La app permite importar un CSV desde el boton de carga. El archivo debe tener estas columnas:

```csv
codigo,nombre,marca,categoria,imagen
P001,Galletas ejemplo,Marca ejemplo,Galletas,/productos/P001.jpg
```

Las imagenes se guardan en:

```text
public/productos/
```

Despues de agregar o cambiar imagenes en `public/productos/`, vuelve a ejecutar:

```powershell
npm.cmd run build
```

## Extraer productos desde el PDF

Para generar una primera base desde el PDF y cargarla en SQLite:

```powershell
python scripts/extract_catalog.py --import-db
```

El extractor genera:

```text
data/extraccion-catalogo/productos_extraidos.csv
data/extraccion-catalogo/productos_sin_imagen.csv
data/extraccion-catalogo/productos_nombre_dudoso.csv
```

Tambien copia los recortes a:

```text
public/productos/
```

## Edicion manual

Cada producto tiene un boton con icono de lapiz. Desde ahi puedes cambiar:

- codigo
- precio

La app valida que el nuevo codigo no exista en otro producto.

Tambien existe endpoint local:

```text
PATCH /api/products/:codigo
```

Ejemplo de cuerpo JSON:

```json
{
  "code": "1066741",
  "price": 48744
}
```

## Informe

El boton de descarga genera un informe CSV del dia con:

- fecha
- cliente o tienda
- codigo
- producto
- cantidad
- precio unitario
- total por linea

Excel abre este CSV directamente.

La app tambien muestra un informe por fecha dentro del panel de pedido:

- nombre de tienda o cliente
- productos pedidos
- codigo
- cantidad
- precio unitario
- total por producto
- total por tienda

Desde esa misma vista puedes eliminar todos los pedidos de una fecha especifica.
Para eliminar se solicita una clave de 4 digitos. Por defecto es `0000`.

Endpoints disponibles:

```text
GET /api/orders/summary?date=YYYY-MM-DD
DELETE /api/orders?date=YYYY-MM-DD
```

## Extraer precios desde el PDF

Despues de auditar productos e imagenes, los precios se actualizan con:

```powershell
python scripts/extract_prices.py
```

El proceso genera:

```text
data/extraccion-catalogo/precios_auditados.csv
data/extraccion-catalogo/precios_conflictos.csv
data/extraccion-catalogo/precios_faltantes.csv
```

## Cruzar codigos con inventario

El Excel de inventario se analiza con:

```powershell
python scripts/match_inventory_codes.py
```

Genera:

```text
data/extraccion-catalogo/sugerencias_codigos_inventario.csv
data/extraccion-catalogo/actualizaciones_alta_confianza.csv
data/extraccion-catalogo/codigos_catalogo_no_en_inventario.csv
data/extraccion-catalogo/inventario_normalizado.csv
```

## Datos locales

La base local queda en:

```text
data/catalogo.sqlite
```

No se sube nada a internet.
