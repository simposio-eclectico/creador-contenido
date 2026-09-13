# Creador de Contenido (video & lyrics → composiciones para redes)

Herramienta integrada con tres pestañas para convertir videos o carpetas de fotos en contenido listo para redes:

1. **🎨 Composición:** Asocia frases con fotos y compone para formato (Instagram 4:5, cuadrado, story)
2. **🎬 Video:** Procesa un video en fotogramas con embeddings
3. **✂️ Reels:** Extrae automáticamente los momentos más destacados de un video como clips verticales, con subtítulos generados por Whisper

Incluye [selector-fotogramas](../selector-fotogramas) integrado, así que puedes hacer todo en una sola interfaz web.

## Requisitos

- Python 3.9+
- ffmpeg + ffprobe (para procesar videos y extraer reels)
  - Para subtítulos quemados en los reels, se recomienda `brew install ffmpeg-full` (incluye `drawtext`/libfreetype); se detecta automáticamente y se prioriza sobre el ffmpeg normal si está instalado. Sin esto, el sistema sigue funcionando pero solo entrega el archivo `.srt` sin quemar
- GPU recomendada (NVIDIA CUDA o Apple Metal para acelerar embeddings CLIP y transcripción Whisper)

```bash
python3 -m pip install -r requirements.txt
```

La primera vez que uses subtítulos, Whisper descargará el modelo elegido (~75MB-500MB según el tamaño) a `~/.cache/whisper`.

## Interfaz web (recomendado)

La forma más fácil es usar la interfaz web con tres pestañas integradas:

```bash
./run.sh
# o: python3 server.py
```

Luego abre `http://localhost:5000` en tu navegador. Verás tres pestañas:

### 🎨 Pestaña Composición
1. **Carpeta de fotos:** usa la salida de la pestaña Video, o una carpeta local (con o sin `metadata.json`)
2. **Letra:** pega tus frases (una por línea) o sube archivo `.txt`
3. **Formato:** Instagram 4:5, cuadrado, story
4. **Opciones:** modo automático/manual, device (GPU/CPU), top-k, detectar rostros, favoritos, etc.
5. El servidor automáticamente:
   - Si la carpeta NO tiene `metadata.json` → corre `generate_from_folder.py` primero
   - Si la carpeta SÍ tiene `metadata.json` → va directo a `main.py`
   - Genera `review.html` interactivo donde puedes elegir imagen, tipografía, color y efecto por frase

### 🎬 Pestaña Video
1. Sube un archivo de video (MP4, MOV, MKV, etc.)
2. El sistema procesa el video en fotogramas con embeddings CLIP
3. Genera: `metadata.json`, thumbnails, visor interactivo
4. Al terminar, botón "✓ Usar en Composición" te lleva a la pestaña Composición

### ✂️ Pestaña Reels
1. Sube un archivo de video
2. Configura:
   - **Duración de cada reel:** 15-60 segundos
   - **Cantidad de reels:** cuántos clips extraer
   - **Peso audio vs. visual:** qué tanto influye el volumen/energía del audio (risas, aplausos, picos) vs. el movimiento e interés visual de la escena al elegir los momentos destacados
   - **Formato:** story (1080x1920) o cuadrado (1080x1080)
   - **Subtítulos:** activa/desactiva, elige el idioma del audio (español, inglés, portugués, francés, italiano, alemán), el modelo Whisper (tiny/base/small) y la tipografía para quemarlos (default **IM Fell**, la misma que usa el editor de composiciones; también Georgia, Arial, Helvetica, Courier, Impact)
   - **Fadeout:** activa/desactiva el desvanecido de audio e imagen en los últimos segundos de cada reel, elige la duración, y si el video se desvanece a negro o hacia una imagen fija que subís (ideal para un logo/outro)
3. El sistema:
   - Analiza audio (energía/picos de volumen) y video (entropía, contraste, movimiento, saliencia) del clip completo
   - Combina ambas señales según el peso elegido y selecciona los mejores momentos no superpuestos
   - Recorta cada momento al formato vertical elegido (esta versión, **sin subtítulos**, siempre queda disponible para descargar)
   - Si activaste fadeout, desvanece audio y video en los últimos segundos (a negro o hacia la imagen elegida)
   - Si activaste subtítulos, transcribe con Whisper (local, sin conexión a internet) y te muestra el texto de cada reel para que lo revises/corrijas antes de quemarlo — Whisper no siempre transcribe perfecto, sobre todo con modelos rápidos (`tiny`) o audio ruidoso
4. **Revisa y edita los subtítulos:** para cada reel ves una vista previa (sin subtítulos) y el texto transcrito dividido en segmentos con su tiempo; corregí lo que haga falta y presioná "Confirmar y quemar subtítulos"
5. El sistema quema los subtítulos (con tu texto corregido) sobre cada clip y actualiza el `.srt`
6. Descarga cada reel: la versión sin subtítulos (siempre disponible), la versión con subtítulos quemados (si confirmaste el paso anterior y tu ffmpeg soporta `drawtext`, ver Requisitos), o el `.srt` para editar/subir aparte

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

#### 2d. Extraer reels destacados (CLI)

```bash
python3 reel_extractor/extract.py \
  --input video.mp4 \
  --output ./reels_output \
  --duration 30 \
  --count 3 \
  --audio-weight 0.5 \
  --format story \
  --subtitles \
  --whisper-model base \
  --subtitle-font im_fell \
  --fade-out 3 \
  --fade-target image \
  --fade-image outro.png
```

Parámetros:

```bash
python3 reel_extractor/extract.py --input video.mp4 --output salida/ \
  --duration 30 \          # duracion de cada reel en segundos (15-60)
  --count 3 \              # cantidad de reels a extraer
  --audio-weight 0.5 \     # 0=solo visual, 1=solo audio, al elegir momentos destacados
  --format story \         # story (1080x1920) | square (1080x1080)
  --subtitles \            # genera .srt + version con subtitulos quemados
  --whisper-model base \   # tiny | base | small
  --language es \          # idioma del audio para Whisper (es, en, pt, fr, it, de, ...)
  --subtitle-font im_fell \ # im_fell (default) | georgia | arial | helvetica | courier | impact
  --fade-out 3 \           # segundos de fadeout audio+video al final (0 = desactivado)
  --fade-target black \    # black (fundido a negro) | image (fundido a --fade-image)
  --fade-image outro.png \ # requerido solo si --fade-target=image
  --fade-image-fit cover \ # cover | contain-width | contain-height (default: cover)
  --fade-background-color black \ # color para fondos en contain mode
  --skip-burn              # solo genera .srt (sin quemar), para revisar/editar el texto antes
```

#### Modos de fundido a imagen (`--fade-target=image`)

- **`--fade-image-fit cover`** (default): La imagen se escala y recorta para rellenar completamente el área (como CSS `background-size: cover`). Puede recortar los bordes de la imagen.
- **`--fade-image-fit contain-width`**: La imagen se escala para que coincida el ancho, manteniendo su proporción. El alto puede quedar vacío, que se rellena con el color de fondo.
- **`--fade-image-fit contain-height`**: La imagen se escala para que coincida el alto, manteniendo su proporción. El ancho puede quedar vacío, que se rellena con el color de fondo.
- **`--fade-background-color`**: Color de fondo para usar en los modos `contain-*` (ej: `black`, `ffffff` para blanco, `ff0000` para rojo). Default: `black`.

El fundido ocurre de forma suave durante los últimos `--fade-out` segundos: el video original se desvanece gradualmente mientras la imagen aparece simultáneamente.

### Editar subtítulos antes de quemarlos (CLI)

Si usaste `--skip-burn`, el `.srt` y el texto transcrito (por reel) quedan en `metadata.json`
sin quemar en el video. Para editar el texto y quemarlo después, sin tener que repetir la
detección de highlights ni la transcripción (los pasos más lentos):

```bash
# 1. Edita el texto en un JSON: [{"start": 0.0, "end": 8.0, "text": "texto corregido"}]
# 2. Quema los subtítulos editados sobre el clip ya generado:
python3 reel_extractor/burn_subs.py \
  --clip reels_output/clips/01.mp4 \
  --segments segmentos_editados.json \
  --output reels_output/clips/01_subtitled.mp4 \
  --srt-output reels_output/subs/01.srt \
  --font im_fell
```

Genera:

```
reels_output/
├── clips/
│   ├── 01.mp4              # reel #1 (vertical, sin subtitulos)
│   ├── 01_subtitled.mp4    # reel #1 con subtitulos quemados (si --subtitles y ffmpeg soporta drawtext)
│   └── ...
├── subs/
│   ├── 01.srt              # subtitulos del reel #1 (si --subtitles)
│   └── ...
└── metadata.json           # ventanas elegidas, scores, rutas de cada archivo
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
