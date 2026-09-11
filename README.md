# Creador de Contenido (video & lyrics → composiciones para redes)

Herramienta integrada de dos etapas para convertir videos o carpetas de fotos en contenido listo para redes:

1. **🎬 Pestaña 1 (Video):** Procesa un video en fotogramas con embeddings
2. **🎨 Pestaña 2 (Composición):** Asocia frases con fotos y compone para formato (Instagram 4:5, cuadrado, story)

Incluye [selector-fotogramas](../selector-fotogramas) integrado, así que puedes hacer todo en una sola interfaz web.

## Requisitos

- Python 3.9+
- ffmpeg + ffprobe (para procesar videos)
- GPU recomendada (NVIDIA CUDA o Apple Metal para acelerar embeddings CLIP)

```bash
python3 -m pip install -r requirements.txt
```

## Interfaz web (recomendado)

La forma más fácil es usar la interfaz web con dos pestañas integradas:

```bash
./run.sh
# o: python3 server.py
```

Luego abre `http://localhost:5000` en tu navegador. Verás dos pestañas:

### 🎬 Pestaña 1: Video
1. Sube un archivo de video (MP4, MOV, MKV, etc.)
2. El sistema procesa el video en fotogramas con embeddings CLIP
3. Genera: `metadata.json`, thumbnails, visor interactivo
4. Al terminar, botón "✓ Usar en Composición" te lleva a la Pestaña 2

### 🎨 Pestaña 2: Composición
1. **Carpeta de fotos:** usa la salida de la Pestaña 1, o una carpeta local (con o sin `metadata.json`)
2. **Letra:** pega tus frases (una por línea) o sube archivo `.txt`
3. **Formato:** Instagram 4:5, cuadrado, story
4. **Opciones:** modo automático/manual, device (GPU/CPU), top-k, detectar rostros, favoritos, etc.
5. El servidor automáticamente:
   - Si la carpeta NO tiene `metadata.json` → corre `generate_from_folder.py` primero
   - Si la carpeta SÍ tiene `metadata.json` → va directo a `main.py`
   - Genera `review.html` interactivo donde puedes elegir imagen, tipografía, color y efecto por frase

## Flujos de uso comunes

### Flujo A: Video → Composición (integrado, recomendado)
```
1. python3 server.py
2. Abre http://localhost:5000
3. Tab "Video": sube tu video MP4/MOV → procesa automáticamente
4. Botón "✓ Usar en Composición" → Tab "Composición"
5. Tab "Composición": pega frases → procesa → review.html
```
**Tiempo total:** 2-10 min (según tamaño video + GPU)

### Flujo B: Carpeta existente → Composición
```
1. python3 server.py
2. Abre http://localhost:5000
3. Tab "Composición": selecciona carpeta de fotos + pega frases
4. Si carpeta NO tiene metadata.json → genera automáticamente
5. review.html listo
```
**Tiempo:** 30s - 5 min (según cantidad fotos)

### Flujo C: Línea de comandos (para scripts/automatización)

Si prefieres usar los scripts directamente desde terminal (útil para CI/CD o batch processing):

#### 2a. Procesar video en CLI

Si prefieres no usar la web, puedes correr selector-fotogramas directamente:

```bash
python3 video_processor/generate.py \
  --input clip.mp4 \
  --output ./mi-video-procesado
```

Genera `metadata.json`, embeddings, thumbs, y visor interactivo en `./mi-video-procesado/`.

#### 2b. Procesar carpeta de fotos en CLI

```bash
python3 generate_from_folder.py \
  --input /ruta/a/carpeta/fotos \
  --output ./mi-galeria-procesada
```

Parámetros:

```bash
python3 generate_from_folder.py --input fotos/ --output salida/ \
  --cluster-eps 0.08 \          # bajo=más fotos diferentes
  --device cuda \               # auto | cpu | cuda | mps
  --no-faces                    # desactiva detección de rostros
```

#### 2c. Componer contenido (CLI)

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

### Modo de seleccion (`--selection-mode`)

| Modo | Que hace |
|---|---|
| `auto` (default) | El algoritmo rankea por similitud CLIP y guarda las `--top-k` mejores fotos por frase |
| `manual` | Todas las fotos quedan como candidatas en todas las frases (sin rankear ni usar CLIP), para elegir a mano en `review.html` |

```bash
python3 main.py --images ./mi-video-review --lyrics letra.txt --selection-mode manual
```

En modo `manual` no se hornea una composicion con texto por cada combinacion
frase x foto (seria carisimo con muchas fotos/frases): el selector de
candidatas en `review.html` muestra la miniatura original de
selector-fotogramas, y `--top-k` se ignora.

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
