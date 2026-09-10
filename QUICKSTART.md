# Guía rápida: Interfaz web

## Ejecutar el servidor

```bash
./run.sh
```

Este script crea un entorno virtual en `.venv/` (si no existe), instala/actualiza
las dependencias y arranca el servidor. Es lo único que necesitas correr cada vez.

### Alternativa manual

```bash
python3 -m pip install -r requirements.txt
python3 server.py
```

Verás:
```
Servidor iniciado en http://localhost:5000
Abre esa URL en tu navegador.
```

## Usar la interfaz

1. **Abre `http://localhost:5000`** en tu navegador.

2. **Rellena el formulario:**
   - **Carpeta:** Ruta absoluta a tus fotos o carpeta procesada (ej: `/Users/tu-usuario/fotos` o `~/fotos`)
   - **Letra:** Puedes:
     - Cargar desde un archivo `.txt` o `.md` (clic en selector de archivo)
     - O pegar directamente las frases, una por línea (en el textarea)
   - **Formato:** Elige el tamaño (Instagram 4:5 es el predeterminado)

3. **Opciones avanzadas** (clic en ⚙️):
   - Device: auto (recomendado), cpu, cuda, mps
   - Candidatas por frase: cuántas opciones mostrar (default 5)
   - Similitud de clustering: qué tan parecidas deben ser dos fotos para agruparlas
   - Otros: favoritos JSON, carpetas de salida personalizadas

4. **Procesar →** Envía el formulario

5. **Mira el log en vivo** mientras se ejecuta:
   - Si no tiene `metadata.json` → corre `generate_from_folder.py` primero
   - Luego corre `main.py` automáticamente
   - Cuando termine → se habilita el botón "📸 Ver resultado"

6. **Ver resultado** → se abre en una nueva pestaña con el `review.html` interactivo

## Ejemplos

### Caso 1: Carpeta ya procesada (con metadata.json)

```
Carpeta: /Users/cristobal/Dropbox/mi-video-review
Letra: [pego mis frases]
Formato: instagram_4_5
Procesar → (salta generate, va directo a main) → ✅
```

### Caso 2: Carpeta de fotos crudas (sin metadata.json)

```
Carpeta: /Users/cristobal/Dropbox/fotos-del-evento
Letra: [pego mis frases]
Formato: square
Procesar → (genera metadata + embeddings) → (corre main) → ✅
```

### Caso 3: Solo procesar fotos, sin composición aún

```
Carpeta: /Users/cristobal/fotos-crudas
Letra: [pego algo temporal]
Procesar → (termina) → inspecciona las fotos con /jobs/<id>/review/index.html
```

## Archivos generados

Dentro de cada job en `jobs/<job_id>/`:
- `log.txt` — todo lo que los scripts imprimieron
- `lyrics.txt` — la letra que pegaste
- `generate_output/` — solo si tuvo que procesar fotos
  - `thumbs/`, `full/`, `metadata.json`, etc.
- `main_output/` — resultado final
  - `review.html` — la interfaz interactiva
  - `compositions/`, `backgrounds/` — miniaturasGeneradas
  - `associations.json` — datos de asociaciones

## Solución de problemas

**"Carpeta no existe"**
- Verifica que la ruta sea absoluta o comience con `~`
- En Mac/Linux usa `/Users/...` o `~/...`

**"Error: generate_from_folder.py falló"**
- Revisa el log para ver qué salió mal (generalmente CLIP, GPU, o archivo corrupto)

**"Error en main.py"**
- Verifica que hayas pegado al menos una frase
- Si pasaste un archivo de favoritos, asegúrate de que exista

**El navegador no muestra el resultado**
- Si cambiaste el puerto en `server.py`, usa ese puerto
- Recarga la página (Cmd+R / Ctrl+R)

## Para terminar el servidor

En la terminal donde corre `python3 server.py`, presiona **Ctrl+C**.

---

¿Preguntas o problemas? Revisa el README.md principal para información más detallada.
