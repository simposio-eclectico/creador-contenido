# Creador de contenido (lyrics → imagenes)

Segunda etapa del flujo, despues de [selector-fotogramas](../selector-fotogramas):
toma una carpeta ya curada (favoritos exportados de ese visor, o directamente
su `metadata.json` completo) y una letra, y propone que imagen va mejor con
cada frase, componiendo el resultado listo para redes.

## Requisitos

- Python 3.9+
- Una carpeta generada por `selector-fotogramas/generate.py` **con embeddings**
  en `metadata.json` (campo `embedding` por fotograma; ver el README de ese
  repo para el schema completo).

```bash
python3 -m pip install -r requirements.txt
```

## Interfaz web (recomendado)

La forma más fácil es usar la interfaz web que maneja todo automáticamente:

```bash
python3 server.py
```

Luego abre `http://localhost:5000` en tu navegador. Desde ahí puedes:

1. Seleccionar una carpeta de fotos (con o sin `metadata.json`).
2. Pegar la letra (frases, una por línea).
3. Elegir formato (Instagram 4:5, cuadrado, story).
4. Configurar opciones avanzadas (device, clustering, detección de rostros, favoritos).
5. El servidor automáticamente:
   - Detecta si la carpeta tiene `metadata.json`.
   - Si no, corre `generate_from_folder.py` primero.
   - Encadena automáticamente a `main.py`.
   - Muestra un log en vivo y al terminar te da acceso al `review.html`.

## Línea de comandos

Si prefieres usar los scripts directamente desde terminal:

### 1. Procesar una carpeta de fotos sin metadata

Si tienes una carpeta de fotos que no ha sido procesada por selector-fotogramas,
puedes usar `generate_from_folder.py` para prepararla:

```bash
python3 generate_from_folder.py \
  --input /ruta/a/carpeta/fotos \
  --output ./mi-galeria-procesada
```

Esto genera la estructura de `metadata.json` con embeddings OpenCLIP y clustering.

Parámetros útiles:

```bash
python3 generate_from_folder.py --input fotos/ --output salida/ \
  --cluster-eps 0.08 \          # distancia coseno para agrupar duplicados (bajo=mas fotos)
  --no-faces \                  # desactiva deteccion de rostros
  --device cuda                 # auto | cpu | cuda | mps
```

### 2. Componer el contenido

```bash
python3 main.py \
  --images ./mi-galeria-procesada \
  --lyrics letra.txt \
  --format instagram_4_5
```

## Uso

```bash
python3 main.py \
  --images /ruta/a/mi-video-review \
  --lyrics letra.txt \
  --format instagram_4_5
```

`letra.txt` es texto plano, una frase por linea (lineas vacias se ignoran).

Para usar solo los fotogramas marcados como favoritos en el visor de
selector-fotogramas, pasa el respaldo JSON que descargas/sincronizas desde
ahi (bot&oacute;n "Descargar respaldo JSON" o respaldo autom&aacute;tico,
ver el README de selector-fotogramas):

```bash
python3 main.py \
  --images /ruta/a/mi-video-review \
  --favorites /ruta/a/mi-video-review-respaldo.json \
  --lyrics letra.txt
```

Sin `--favorites`, se consideran todos los fotogramas de `metadata.json`.

Sin `--output`, escribe dentro de la propia carpeta de imagenes, en una
subcarpeta `creator/` (por ejemplo `/ruta/a/mi-video-review/creator/`). Pasa
`--output otra/ruta` si preferis otro destino.

Esto genera:

```
mi-video-review/creator/
├── compositions/         # miniatura horneada por candidata (estilo por defecto)
├── backgrounds/          # fondo (recorte + degrade) sin texto, usado por el editor en vivo
├── associations.json     # todas las candidatas por frase, con score/relacion
└── review.html           # editor interactivo: elegir imagen + tipografia/color/efecto
```

### Formatos disponibles (`--format`)

| Nombre | Tamano |
|---|---|
| `instagram_4_5` (default) | 1080x1350 |
| `square` | 1080x1080 |
| `story` | 1080x1920 |

## Como funciona el matching hoy

Cada frase y cada imagen viven en el mismo espacio de embeddings OpenCLIP
(mismo modelo que usa `selector-fotogramas` para no recalcular nada): se
rankean las imagenes por similitud coseno con el texto de la frase.

Eso cubre la relacion **semantica/literal** ("la imagen que mas se parece
conceptualmente a la frase"). Las relaciones **asociativa** y **contrapunto**
que describe el problema original necesitan un paso adicional de
interpretacion (LLM) que hoy **no esta implementado** — es intencional: el
punto de extension es `lyrics_social/matching.py::classify_relation()`, que
por ahora siempre devuelve `"semantica"`. Conectar ahi un LLM (dado el texto
de la frase + candidatas) para reclasificar/reordenar es el siguiente paso
logico, una vez que se decida que proveedor usar.

## Composicion

`lyrics_social/composer.py` recorta la imagen al formato pedido y ubica la
zona de texto (con un degrade sutil, no una barra opaca) evitando el tercio
donde `face_position` (de `metadata.json`) indica que hay una cara. Es una
regla simple, no un layout engine.

El texto en si no se hornea en Python salvo para las miniaturas de
candidatas: `review.html` lo dibuja en un `<canvas>` sobre el fondo
(`backgrounds/`), asi que se puede elegir tipografia, color, y efecto
(contorno, sombra de color, blur, pixelado) por frase con vista previa
instantanea, y descargar el PNG final ya con ese estilo aplicado.

## Schema de `associations.json`

```json
{
  "lyrics_source": "letra.txt",
  "images_source": "/ruta/a/mi-video-review",
  "format": "instagram_4_5",
  "lines": [
    {
      "index": 0,
      "line": "No queda nada detras",
      "candidates": [
        {
          "image_id": 73,
          "image": "full/00073.jpg",
          "clip_score": 0.31,
          "confidence": 1.0,
          "relation": "semantica",
          "composed": "compositions/001_73.jpg",
          "background": "backgrounds/001_73.jpg",
          "text_anchor": "bottom"
        }
      ]
    }
  ]
}
```

`confidence` esta normalizado 0-1 dentro del pool de candidatas de esa
frase (no comparable entre frases); `clip_score` es la similitud coseno
cruda.

## Pendiente / no implementado a proposito

- Clasificacion asociativa/contrapunto vía LLM (ver seccion de matching).
- Persistir la eleccion hecha en `review.html` de vuelta a `associations.json`
  (hoy la eleccion vive solo en el navegador; "Copiar seleccion" en la barra
  superior copia el JSON con imagen/tipografia/color/efecto elegidos por
  linea para guardarlo a mano mientras tanto).
