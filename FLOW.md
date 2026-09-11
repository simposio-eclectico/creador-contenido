# Flujo de uso: de video y fotos a contenido

## 🎯 Nuevo flujo integrado (recomendado)

Ahora puedes hacer todo en una sola interfaz web con dos pestañas:

### Flujo A: Video → Composición (2 pestañas)

```
PASO 1: python3 server.py
        Abre http://localhost:5000

PASO 2: TAB "🎬 Video"
        Sube tu video (MP4/MOV/MKV)
        ↓
        Sistema procesa en background:
        - Extrae fotogramas
        - Calcula embeddings CLIP
        - Agrupa casi-duplicados
        - Detecta rostros
        ↓
        (⏳ 30s - 5 min según tamaño video + GPU)

PASO 3: Cuando termine → Botón "✓ Usar en Composición"
        ↓
        Auto-cambia a TAB "🎨 Composición"
        Folder field pre-lleno con output de video

PASO 4: TAB "🎨 Composición"
        Pega tus frases (una por línea)
        Elige formato (Instagram 4:5, square, story)
        Procesar →
        ↓
        Sistema:
        - Rankea fotos por similitud con cada frase (CLIP)
        - Compone formato final evitando caras
        - Genera review.html interactivo
        ↓
        (⏳ 10-30s)

PASO 5: "📸 Ver resultado" → review.html
        Para cada frase:
        - Ves top 5 candidatas
        - Eliges color, fuente, efecto
        - Descargas PNG listo para Instagram

TIEMPO TOTAL: 1-10 minutos (todo en la web)
```

---

## 📝 Flujo B: Carpeta existente → Composición

Si ya tienes fotos procesadas o una carpeta de fotos crudas:

```
TAB "🎨 Composición"
  ① Folder: /ruta/a/mi-carpeta-fotos
  ② Letra: [tus frases]
  ③ Procesar →
     ↓
     ¿Tiene metadata.json?
     ├─ SÍ → va directo a main.py (~10-30s)
     └─ NO → corre generate_from_folder.py primero
             (procesa fotos crudas, ~2-5 min)
  ④ "📸 Ver resultado"
```

---

## 🎬 Escenario antiguo (CLI, aún funciona): Tienes un video

**(Solo si prefieres CLI)**

```bash
# Paso 1: Procesar video con selector-fotogramas (CLI)
python3 video_processor/generate.py \
  --input video.mp4 \
  --output mi-video-procesado/

# Paso 2: Abrir web para composición
python3 server.py
# Tab "Composición":
#   Folder: ./mi-video-procesado
#   Letra: [tus frases]
#   Procesar → review.html
```

**Tiempo aprox:** Video: 1-3 min + Composición: 10-30s

---

## 📸 Escenario antiguo (CLI): Tienes fotos crudas (sin procesar)

**(Ahora recomendamos usar la web, pero aquí va el flujo CLI si lo prefieres)**

```bash
# Paso 1: Procesar carpeta de fotos crudas (CLI)
python3 generate_from_folder.py \
  --input /Users/tu-usuario/fotos-evento \
  --output ./fotos-evento-procesado

# Paso 2: Usar en web
python3 server.py
# Tab "Composición":
#   Folder: ./fotos-evento-procesado
#   Letra: [tus frases]
#   Procesar → review.html
```

O si quieres todo en CLI:

```bash
python3 main.py \
  --images ./fotos-evento-procesado \
  --lyrics letra.txt \
  --format instagram_4_5
```

**Tiempo aprox:** 2-5 min (generar embeddings toma tiempo; GPU acelera muchísimo)

---

## 🎨 Escenario 3: Carpeta ya procesada + nueva letra

**Ahora es muy simple:**

```
python3 server.py
Abre http://localhost:5000

Tab "Composición":
  Folder: /ruta/fotogramas-evento (con metadata.json)
  Letra: [NUEVAS frases]
  Procesar →
  
El servidor:
  ✓ Detecta metadata.json
  ✓ Salta generate_from_folder
  ✓ Va directo a main.py
  ✓ Genera nuevo review.html

[resultado en ~10-30s]
```

**Tiempo aprox:** 10-30s (solo main.py, sin recalcular embeddings)

---

## 🔄 Flujo detallado en el navegador (dos pestañas)

```
┌──────────────────────────────────────────────┐
│ http://localhost:5000                        │
├──────────────────┬──────────────────────────┤
│ [🎬 Video]      [🎨 Composición]            │
├──────────────────┴──────────────────────────┤
│                                              │
│ TAB 1: VIDEO                                 │
│ ┌──────────────────────────────────────┐    │
│ │ Selecciona archivo: [sube_video.mp4] │    │
│ │           [Procesar video →]         │    │
│ └──────────────────────────────────────┘    │
│                                              │
│ ESTADO: 🎬 Procesando video...              │
│ (log en vivo)                               │
│ ✓ Extrayendo fotogramas                    │
│ ✓ Embeddings CLIP                          │
│ ✓ Clustering DBSCAN                        │
│ ✓ Detección de rostros                     │
│                                              │
│ ✅ Listo!                                    │
│ [✓ Usar en Composición →]                  │
│                                              │
└──────────────────────────────────────────────┘
        ↓ clic en "Usar en Composición"
        Auto-cambia a TAB 2
┌──────────────────────────────────────────────┐
│ http://localhost:5000                        │
├──────────────────┬──────────────────────────┤
│ [🎬 Video]      [🎨 Composición] ← ACTIVO   │
├──────────────────┴──────────────────────────┤
│                                              │
│ TAB 2: COMPOSICIÓN                           │
│ ┌──────────────────────────────────────┐    │
│ │ Carpeta: [/jobs/.../video_output] ✓ │    │
│ │ Letra: [Frase 1                   ] │    │
│ │        [Frase 2                   ] │    │
│ │ Formato: [instagram 4:5 ✓]         │    │
│ │        [Procesar →]                │    │
│ └──────────────────────────────────────┘    │
│                                              │
│ ESTADO: ⏳ Pendiente                         │
│ ETAPA:  Iniciando...                       │
│                                              │
│ (log en vivo)                               │
│ ✓ Carpeta tiene metadata.json              │
│ Ejecutando main.py...                      │
│ Rankeando candidatas...                    │
│ Componiendo formato...                     │
│                                              │
│ ✅ Listo!                                    │
│     [📸 Ver resultado →]                    │
│     [Volver a intentar]                     │
│                                              │
└──────────────────────────────────────────────┘
        ↓ clic en "Ver resultado →"
┌──────────────────────────────────────────────┐
│ REVIEW.HTML (nueva pestaña)                  │
│                                              │
│ Galería interactiva:                         │
│ • Miniatura de cada frase                   │
│ • Top 5 candidatas por frase                │
│ • Editor: tipografía, color, efecto         │
│ • Preview en vivo                           │
│ • [Descargar PNG]                           │
│                                              │
└──────────────────────────────────────────────┘
```

---

## 🎯 Caso de uso real: producción ágil de contenido

```
LUNES:
  Grabas video del evento (~5 min)

MARTES:
  ① python3 server.py
  ② Abres http://localhost:5000
  
  TAB "Video":
  ③ Subes video del evento
  ④ Procesar → [esperas 2-5 min]
  ⑤ ✓ Usar en Composición
  
  TAB "Composición" (auto-lleno folder):
  ⑥ Pegas letras de Instagram
  ⑦ Procesar → [esperas 10-30s]
  ⑧ "Ver resultado" → review.html
  
  EDITOR INTERACTIVO:
  ⑨ Para cada frase:
     • Ves 5 candidatas (fotos del video)
     • Eliges color, tipografía, efecto
     • Descargas PNG
  
  ⑩ En 30 minutos: 10 composiciones listas

MIÉRCOLES:
  Subes a Instagram ✨
  
TIEMPO TOTAL: ~1 hora (todo en web)
```

**Ventajas vs antes:**
- ✅ Video + Composición integrados (no 2 herramientas)
- ✅ Sin línea de comandos (todo con clicks)
- ✅ Auto-detección: si carpeta no tiene metadata → procesa automáticamente
- ✅ Log en vivo para saber qué pasa
- ✅ Tab 1 → Tab 2 automático

---

## ❌ Si algo sale mal

### "Carpeta no existe"
- Verifica que pegaste la ruta completa y correcta
- En Mac: `/Users/tu-usuario/Dropbox/fotos` (no `~/Dropbox/fotos`)

### "Error en generate_from_folder.py"
- Revisa el log en la web (verás exactamente dónde falló)
- Posibles causas:
  - Una imagen corrupta (el log te dice cuál)
  - Memoria insuficiente (reduce `cluster-eps` o `device: cpu`)
  - CUDA no funciona (usa `device: auto` o `cpu`)

### "Error en main.py"
- Si pasaste un archivo de favoritos, asegúrate de que exista
- Si dice "No se encontro embedding", la carpeta no tiene los embeddings correctos
- Intenta regenerar: deja la carpeta sin especificar favoritos

### El navegador no muestra el resultado
- Recarga la página (Cmd+R)
- Si sigue sin aparecer, revisa el log más arriba

---

## 📊 Tiempo estimado

| Paso | Con GPU | Sin GPU |
|------|---------|---------|
| generate (100 fotos) | 30-60s | 3-5 min |
| main.py (50 candidatas) | 10-20s | 1-2 min |
| **Total sin metadata** | **1-2 min** | **5-10 min** |
| main.py solo (con metadata) | **10-20s** | **1-2 min** |

GPU = NVIDIA CUDA / Apple Metal
Sin GPU = CPU puro (mucho más lento)

---

## 🔐 Privacidad & Seguridad

- Todo corre **localmente en tu máquina**
- No hay servidor remoto, no hay subidas a internet
- Los jobs se guardan en `jobs/<uuid>/` durante su ejecución
- Puedes borrar `jobs/` en cualquier momento

---

## 💡 Tips

1. **Primera ejecución tarda más** porque CLIP descarga el modelo (~600 MB)
   - Después se cachea, es instantáneo

2. **GPU es criticial** para `generate_from_folder.py`
   - Con GPU: 30-60s por 100 fotos
   - Sin GPU: 3-5 minutos por 100 fotos
   - Detecta automáticamente y usa si está disponible

3. **Agrupación de fotos casi-idénticas**
   - `cluster-eps: 0.08` (default) es un buen balance
   - Más bajo (0.04) = más fotos finales, proceso más lento
   - Más alto (0.15) = menos fotos, más rápido

4. **Favoritos**
   - Si exportaste favoritos del visor de selector-fotogramas, úsalos
   - Reduce de 500 fotos a 50-100 candidatas → main.py más rápido

5. **Opciones avanzadas**
   - Para eventos grandes, `--no-faces` acelera si no necesitas evitar caras
   - `top-k: 10` te da más opciones por frase (default es 5)
