# Arquitectura: Interfaz web

## Componentes

### 1. **Backend: `server.py`** (Flask)

- **Rutas:**
  - `GET /` → sirve `templates/index.html`
  - `POST /api/jobs` → crea un job, valida input, lanza hilo de fondo
  - `GET /api/jobs/<job_id>` → retorna estado del job + cola del log
  - `GET /jobs/<job_id>/review/<path>` → sirve archivos desde `main_output` (con guard contra path traversal)

- **Orquestación de jobs:**
  - `JOBS` dict protegido por `threading.Lock()` — registry global
  - Cada job tiene: `{status, stage, log_path, main_output, review_url, error}`
  - `run_job()` ejecuta en `threading.Thread(daemon=True)` — dos subprocesos secuenciales si es necesario:
    1. `generate_from_folder.py` (solo si falta `metadata.json`)
    2. `main.py` (siempre)
  - Ambos subprocesos redirigen stdout/stderr a `jobs/<job_id>/log.txt`

- **Validaciones (al submit, antes de crear job):**
  - Carpeta existe y es directorio
  - Letra no vacía
  - Si se pasó `favorites_path`, existe

- **Flow de un job:**
  1. `pending` → se crea, se espera iniciar
  2. `running_generate` → si falta `metadata.json`, corre `generate_from_folder.py`
  3. `running_main` → corre `main.py`
  4. `done` → ambos pasos completados, `review_url` disponible
  5. `error` → algún step falló, `error` contiene la razón

### 2. **Frontend: `templates/index.html` + `static/app.js` + `static/style.css`**

- **HTML:** Formulario vanilla, sin framework
  - Input `folder` (ruta absoluta)
  - Textarea `lyrics_text` (letra a pegar)
  - Select `format` (instagram_4_5, square, story)
  - Details `advanced-options` (device, top-k, cluster-eps, no-faces, favoritos, etc.)
  - Botón submit "Procesar →"

- **CSS:** Tema oscuro consistente con `review.py`
  - Colores: fondo #111, acento verde (#4ade80), bordes grises
  - Responsive

- **JavaScript (`app.js`):** Vanilla, cero dependencias
  - Al submit: serializa formulario → POST `/api/jobs` → obtiene `job_id`
  - Inicia `setInterval` de polling cada 1.5s a `GET /api/jobs/<id>`
  - Actualiza badge, stage, log en vivo
  - Al llegar a `done` → muestra link a `review_url`
  - Al llegar a `error` → muestra el mensaje
  - Botón "Volver a intentar" reinicia el formulario

### 3. **Scripts sin modificar (reutilizados)**

- `generate_from_folder.py` — procesa carpeta de fotos crudas
- `main.py` — compone contenido con letra
- `lyrics_social/*` — módulos auxiliares

### 4. **Estructura de directorios en runtime**

```
jobs/                          # gitignored
  <job_id>/
    log.txt                    # stdout+stderr de ambos scripts
    lyrics.txt                 # letra pegada (escrita aquí)
    generate_output/           # solo si se corrió generate
      thumbs/, full/, metadata.json, etc.
    main_output/               # resultado final
      review.html              # lo que ves en el navegador
      compositions/
      backgrounds/
      associations.json
```

## Flow: carpeta SIN metadata.json

```
Usuario rellena formulario
    ↓
POST /api/jobs {folder: "/ruta/fotos", lyrics_text: "...", ...}
    ↓
Validaciones OK → crea job_id, inicia hilo de fondo
    ↓
Backend: detect falta metadata.json
    ↓
Corre: generate_from_folder.py --input /ruta/fotos --output /ruta/fotos_procesado
    ↓
Si returncode != 0 → status:error
Si ok → images_dir = /ruta/fotos_procesado
    ↓
Corre: main.py --images /ruta/fotos_procesado --lyrics jobs/<id>/lyrics.txt ...
    ↓
Si returncode != 0 → status:error
Si ok → review_url = /jobs/<id>/review/review.html
    ↓
Frontend: polling ve status:done, revela link
    ↓
Usuario hace clic → GET /jobs/<id>/review/review.html
```

## Flow: carpeta CON metadata.json

```
Usuario rellena formulario
    ↓
POST /api/jobs {folder: "/ruta/procesada", ...}
    ↓
Validaciones OK → crea job_id, inicia hilo
    ↓
Backend: detect metadata.json existe
    ↓
Salta generate, va directo a main.py
    ↓
Corre: main.py --images /ruta/procesada ...
    ↓
[resto igual]
```

## Seguridad

- **Path traversal:** ruta de servido de `review.html` valida que `target.is_relative_to(base)` antes de `send_from_directory()`
- **Inyección de comandos:** todas las rutas/argumentos se pasan como listas a `subprocess.run()` (no se usan shells)
- **Validación de entrada:** `folder` y `lyrics_text` se validan antes de crear el job; `favorites_path` se comprueba que exista
- **Aislamiento de jobs:** cada job tiene su propio directorio + id único (uuid4), sin colisiones

## Concurrencia

- Múltiples jobs pueden correr en paralelo (cada uno en su propio hilo + directorio)
- GPU/CPU se comparten entre procesos (es una limitación de recursos, no de corrección)
- `JOBS_LOCK` protege lecturas/escrituras del registry, pero los subprocesos corren libres
- Si se quiere limitar a 1 job a la vez, se puede agregar un semáforo

## Extensiones futuras

1. **WebSockets en lugar de polling:** cambiar `setInterval` por `WebSocket` para log en vivo sin latencia
2. **Base de datos:** guardar jobs en SQLite en lugar de dict en memoria (persiste reinicio del servidor)
3. **Autenticación:** si múltiples usuarios acceden remotamente
4. **Límite de concurrencia:** semáforo para máximo N jobs simultáneos
5. **Caché de embeddings:** reutilizar CLIP embeddings entre jobs si la carpeta es la misma
6. **UI mejorada:** progress bar, preview de fotos candidatas, etc.
