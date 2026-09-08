# Flujo de uso: de fotos a contenido

## 🎬 Escenario 1: Tienes un video (estándar)

```
1. selector-fotogramas/
   ├── generate.py --input video.mp4 --output mi-video-procesado/
   └── (genera metadata.json con embeddings + thumbs + full)

2. creador-contenido/
   ├── server.py
   │   └── http://localhost:5000
   │       Carpeta: /ruta/a/mi-video-procesado
   │       Letra: [tus frases]
   │       Procesar →
   └── (automáticamente: salta generate, va directo a main.py)
       └── Resultado: review.html interactivo
```

**Tiempo aprox:** 30s - 2 min (según cantidad de fotos y GPU disponible)

---

## 📸 Escenario 2: Tienes fotos crudas (sin procesar)

```
1. Carpeta local con fotos:
   /Users/tu-usuario/Dropbox/fotos-evento/
   ├── IMG_0001.jpg
   ├── IMG_0002.jpg
   ├── ... (100+ fotos)
   └── (SIN metadata.json)

2. creador-contenido/
   ├── server.py
   │   └── http://localhost:5000
   │       Carpeta: /Users/tu-usuario/Dropbox/fotos-evento
   │       Letra: [tus frases]
   │       Procesar →
   │
   ├── El servidor automáticamente:
   │   ├── Detecta que NO hay metadata.json
   │   ├── Corre: generate_from_folder.py
   │   │   └── Crea: /Users/tu-usuario/Dropbox/fotos-evento_procesado/
   │   │       ├── metadata.json (con embeddings)
   │   │       ├── thumbs/
   │   │       ├── full/
   │   │       └── selected/
   │   │
   │   └── Corre: main.py
   │       └── Resultado en: fotos-evento_procesado/creator/
   │           └── review.html interactivo
   │
   └── Tú ves el log en vivo:
       Procesando carpeta de fotos...
       ✓ Encontradas 245 imagenes
       ✓ Metricas visuales
       ✓ Embeddings CLIP
       ✓ Agrupando casi-duplicados
       ✓ Deteccion de rostros
       245 imagenes -> 73 fotogramas finales
       
       ✓ Generacion completada
       
       Ejecutando main.py...
       Rankeando candidatas por frase...
       Componiendo formato instagram_4_5...
       ✓ Pipeline completado con éxito
       
       [review.html listo para ver]
```

**Tiempo aprox:** 2-5 min (generar embeddings toma tiempo; GPU acelera muchísimo)

---

## 🎨 Escenario 3: Carpeta ya procesada pero necesitas nueva letra

```
1. Tienes /ruta/fotogramas-evento/ con metadata.json previo

2. creador-contenido/
   ├── server.py → http://localhost:5000
   │
   ├── Formulario:
   │   Carpeta: /ruta/fotogramas-evento
   │   Letra: [NUEVAS frases]
   │   Procesar →
   │
   ├── El servidor:
   │   ├── Detecta metadata.json ✓ existe
   │   ├── Salta generate (va directo a main.py)
   │   ├── Corre main.py con la nueva letra
   │   └── Genera nuevo review.html
   │
   └── [resultado en ~30s]
```

**Tiempo aprox:** 10-30s (solo main.py, sin recalcular embeddings)

---

## 🔄 Flujo detallado en el navegador

```
┌─────────────────────────────────────────┐
│ PÁGINA: http://localhost:5000           │
├─────────────────────────────────────────┤
│                                         │
│ 📁 Ruta de carpeta:   [/Users/...    ] │
│ 📝 Letra:             [frase 1...   ] │
│ 📐 Formato:           [instagram 4:5] │
│ ⚙️  Opciones avanzadas (⏺)              │
│                                         │
│                [Procesar →]             │
│                                         │
└─────────────────────────────────────────┘
            ↓ clic en "Procesar →"
┌─────────────────────────────────────────┐
│ ESTADO: ⏳ Pendiente                      │
│ ETAPA:  Iniciando...                   │
│                                         │
│ (log en vivo)                           │
│ ✓ Carpeta ya tiene metadata.json       │
│ Ejecutando main.py...                  │
│ Rankeando candidatas por frase...      │
│ Componiendo formato instagram_4_5...   │
│ ...                                     │
│                                         │
│                                         │
│           [esperando...]                │
│                                         │
└─────────────────────────────────────────┘
            ↓ después de N segundos
┌─────────────────────────────────────────┐
│ ESTADO: ✅ Listo                         │
│ ETAPA:  (completado)                   │
│                                         │
│ (log completo)                          │
│ ✓ Generación completada                │
│ ✓ Pipeline completado con éxito        │
│                                         │
│     [📸 Ver resultado →]                │
│ (abre review.html en nueva pestaña)    │
│                                         │
│     [Volver a intentar]                 │
│                                         │
└─────────────────────────────────────────┘
            ↓ clic en "Ver resultado →"
┌─────────────────────────────────────────┐
│ REVIEW.HTML (nueva pestaña)             │
│                                         │
│ Galería interactiva con:                │
│ • Miniatura de cada frase               │
│ • Top 5 candidatas por frase            │
│ • Editor de tipografía en vivo          │
│ • Preview de composición                │
│ • Botón "Descargar PNG"                 │
│                                         │
└─────────────────────────────────────────┘
```

---

## 🎯 Caso de uso real: evento de fotos

```
LUNES:
  Revisas 500 fotos del evento con selector-fotogramas
  → Marcas 200 como favoritos
  → Descargas respaldo JSON

MARTES:
  Escribes letras para Instagram

MIÉRCOLES:
  ① python3 server.py
  ② Abres http://localhost:5000
  ③ Pegues tu lista de letras
  ④ Seleccionas archivo de favoritos (respaldo.json)
  ⑤ Eliges formato + opciones
  ⑥ Procesar →
  ⑦ Esperas a que termine
  ⑧ Haces clic en "Ver resultado"
  ⑨ Para cada frase:
     • Ves 5 candidatas
     • Eliges color, fuente, efecto
     • Descargas PNG listo para Instagram
  ⑩ En 10 minutos tienes todas tus piezas compostas.

JUEVES:
  Subes a Instagram ✨
```

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
