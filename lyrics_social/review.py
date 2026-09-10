"""Genera review.html: por frase, elegir la imagen candidata, reencuadrar la
foto (arrastrando sobre la vista previa) y editar el estilo del texto
(tipografia, color, efecto, posicion) con vista previa instantanea.

Tanto el recorte "cover" de la foto (replicando composer.py::_cover_crop) como
el degrade y el texto se dibujan en un <canvas> sobre la foto original sin
recortar (campo "source" de metadata.json), usando el Canvas 2D API del
navegador, asi que arrastrar la foto o cambiar cualquier control redibuja al
instante sin volver a llamar a Python. "Descargar PNG" vuelve a dibujar a
resolucion completa y dispara la descarga.
"""
import html
import json
from pathlib import Path

from .composer import BAND_FRAC, FORMATS

FONTS = [
    ("'IM Fell DW Pica', Georgia, serif", "IM Fell DW Pica"),
    ("Arial, Helvetica, sans-serif", "Arial"),
    ("Georgia, 'Times New Roman', serif", "Georgia"),
    ("'Courier New', monospace", "Courier"),
    ("Impact, 'Arial Narrow', sans-serif", "Impact"),
    ("'Helvetica Neue', Helvetica, sans-serif", "Helvetica"),
]

TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Revision de asociaciones</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IM+Fell+DW+Pica&display=swap" rel="stylesheet">
<style>
  body {{ font-family: system-ui, sans-serif; background: #111; color: #eee; margin: 2rem; }}
  h1 {{ font-weight: 500; }}
  .line {{ display: flex; gap: 2rem; margin-bottom: 3rem; border-bottom: 1px solid #333; padding-bottom: 2rem; align-items: flex-start; flex-wrap: wrap; }}
  .preview {{ flex: 0 0 auto; text-align: center; }}
  .preview canvas {{ width: 260px; height: auto; border-radius: 8px; display: block; background: #000; }}
  .preview button {{ margin-top: 0.5rem; width: 100%; }}
  .panel {{ flex: 1; min-width: 320px; }}
  .panel h2 {{ font-weight: 400; margin-top: 0; }}
  .candidates {{ display: flex; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 1rem; }}
  .thumb {{ width: 90px; cursor: pointer; border: 2px solid transparent; border-radius: 6px; padding: 3px; }}
  .thumb img {{ width: 100%; border-radius: 4px; display: block; }}
  .thumb .meta {{ font-size: 0.65rem; color: #aaa; margin-top: 0.2rem; }}
  .thumb.selected {{ border-color: #4ade80; }}
  .controls {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.75rem; align-items: end; }}
  .controls label {{ display: block; font-size: 0.75rem; color: #aaa; margin-bottom: 0.25rem; }}
  .controls select, .controls input[type=color] {{ width: 100%; padding: 0.3rem; }}
  .controls input[type=range] {{ width: 100%; }}
  .effect-color, .intensity {{ display: none; }}
  .toolbar {{ margin-bottom: 1.5rem; }}
  button {{ background: #4ade80; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; font-weight: 600; }}
  .text-edit {{ width: 100%; box-sizing: border-box; resize: vertical; min-height: 3.2rem; background: #1a1a1a; color: #eee; border: 1px solid #333; border-radius: 4px; padding: 0.5rem; font-family: inherit; font-size: 0.9rem; margin-bottom: 1rem; }}
  .align-group {{ display: flex; gap: 0.3rem; }}
  .align-group button {{ flex: 1; background: #2a2a2a; color: #eee; padding: 0.3rem; font-weight: 400; }}
  .align-group button.active {{ background: #4ade80; color: #111; font-weight: 600; }}
  .drag-hint {{ font-size: 0.65rem; color: #777; margin-top: 0.4rem; }}
  .preview canvas {{ cursor: move; }}
</style>
</head>
<body>
<h1>Asociaciones frase &rarr; imagen</h1>
<p>Eleg&iacute; la imagen y el estilo del texto por frase; todo se redibuja al instante en el navegador.</p>
<div class="toolbar"><button onclick="copySelection()">Copiar selecci&oacute;n actual (JSON)</button></div>
{lines}
<script>
const DATA = {data_json};
const CANVAS_W = {canvas_w};
const CANVAS_H = {canvas_h};
const BAND_FRAC = {band_frac};
const PREVIEW_SCALE = 0.5;

const FONTS = {fonts_json};

const bgCache = {{}};
const state = {{}};

function loadImage(src) {{
  if (!bgCache[src]) {{
    bgCache[src] = new Promise(resolve => {{
      const img = new Image();
      img.onload = () => resolve(img);
      img.src = src;
    }});
  }}
  return bgCache[src];
}}

function wrapParagraph(ctx, text, maxWidth) {{
  const words = text.split(" ");
  const lines = [];
  let current = "";
  for (const word of words) {{
    const trial = current ? current + " " + word : word;
    if (current && ctx.measureText(trial).width > maxWidth) {{
      lines.push(current);
      current = word;
    }} else {{
      current = trial;
    }}
  }}
  lines.push(current);
  return lines;
}}

function wrapText(ctx, text, maxWidth) {{
  return text.split("\\n").flatMap(paragraph => wrapParagraph(ctx, paragraph, maxWidth));
}}

function drawPixelatedText(ctx, w, h, lines, fontSpec, lineHeight, startY, color, intensity, cx, align, opacity, letterSpacing, wordSpacing) {{
  const off = document.createElement("canvas");
  off.width = w; off.height = h;
  const octx = off.getContext("2d");
  octx.font = fontSpec;
  octx.textAlign = align;
  octx.letterSpacing = `${{letterSpacing || 0}}px`;
  octx.wordSpacing = `${{wordSpacing || 0}}px`;
  octx.fillStyle = color;
  octx.lineWidth = Math.max(2, w * 0.006);
  octx.strokeStyle = "rgba(0,0,0,0.75)";
  lines.forEach((line, i) => {{
    const y = startY + i * lineHeight;
    octx.strokeText(line, cx, y);
    octx.fillText(line, cx, y);
  }});

  const block = Math.max(2, Math.round(intensity));
  const smallW = Math.max(1, Math.round(w / block));
  const smallH = Math.max(1, Math.round(h / block));
  const tmp = document.createElement("canvas");
  tmp.width = smallW; tmp.height = smallH;
  const tctx = tmp.getContext("2d");
  tctx.imageSmoothingEnabled = false;
  tctx.drawImage(off, 0, 0, smallW, smallH);

  ctx.save();
  ctx.globalAlpha = opacity;
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(tmp, 0, 0, smallW, smallH, 0, 0, w, h);
  ctx.imageSmoothingEnabled = true;
  ctx.restore();
}}

function anchorDefaultY(anchor) {{
  return anchor === "top" ? BAND_FRAC / 2 : 1 - BAND_FRAC / 2;
}}

// Replica _cover_crop de composer.py: calcula el rectangulo fuente (en pixeles
// de la imagen original) que hay que recortar para llenar target_w x target_h
// sin deformar, y cuanto margen de sobra ("maxOffset") queda para paniar.
function coverCropRect(imgW, imgH, targetW, targetH) {{
  const imgRatio = imgW / imgH;
  const targetRatio = targetW / targetH;
  if (imgRatio > targetRatio) {{
    const sh = imgH;
    const sw = sh * targetRatio;
    return {{ axis: "x", sw, sh, maxOffset: imgW - sw }};
  }}
  const sw = imgW;
  const sh = sw / targetRatio;
  return {{ axis: "y", sw, sh, maxOffset: imgH - sh }};
}}

// Posicion inicial del recorte: centrado, salvo sesgo vertical hacia la cara
// (mismo criterio que _cover_crop en Python) cuando hay margen para paniar.
function defaultPan(imgW, imgH, faceCy) {{
  const rect = coverCropRect(imgW, imgH, CANVAS_W, CANVAS_H);
  if (rect.axis === "y" && faceCy != null && rect.maxOffset > 0) {{
    const centerY = faceCy * imgH;
    const y0 = Math.min(Math.max(centerY - rect.sh / 2, 0), rect.maxOffset);
    return {{ panX: 0.5, panY: y0 / rect.maxOffset }};
  }}
  return {{ panX: 0.5, panY: 0.5 }};
}}

function drawCover(ctx, img, w, h, panX, panY) {{
  const rect = coverCropRect(img.naturalWidth, img.naturalHeight, w, h);
  let sx = 0, sy = 0;
  if (rect.axis === "x") {{
    sx = rect.maxOffset * panX;
  }} else {{
    sy = rect.maxOffset * panY;
  }}
  ctx.drawImage(img, sx, sy, rect.sw, rect.sh, 0, 0, w, h);
}}

// Replica _vertical_gradient de composer.py con un gradiente de canvas.
function drawScrim(ctx, w, h, anchor) {{
  const bandFrac = Math.min(1, BAND_FRAC);
  const maxAlpha = 190 / 255;
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  if (anchor === "top") {{
    grad.addColorStop(0, `rgba(0,0,0,${{maxAlpha}})`);
    grad.addColorStop(bandFrac, "rgba(0,0,0,0)");
    grad.addColorStop(1, "rgba(0,0,0,0)");
  }} else {{
    grad.addColorStop(0, "rgba(0,0,0,0)");
    grad.addColorStop(1 - bandFrac, "rgba(0,0,0,0)");
    grad.addColorStop(1, `rgba(0,0,0,${{maxAlpha}})`);
  }}
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, w, h);
}}

function drawText(ctx, w, h, text, s) {{
  const fontFrac = s.fontSize != null ? s.fontSize : 0.075;
  const fontSize = Math.round(w * fontFrac);
  const fontSpec = `bold ${{fontSize}}px ${{s.font}}`;
  const align = s.align || "center";
  const opacity = s.opacity != null ? s.opacity : 1;
  const letterSpacing = Math.round((s.letterSpacing != null ? s.letterSpacing : 0) * w);
  const wordSpacing = Math.round((s.wordSpacing != null ? s.wordSpacing : 0) * w);
  const lineHeightMult = s.lineHeightMult != null ? s.lineHeightMult : 1.25;
  ctx.font = fontSpec;
  ctx.textAlign = align;
  ctx.letterSpacing = `${{letterSpacing}}px`;
  ctx.wordSpacing = `${{wordSpacing}}px`;
  const lines = wrapText(ctx, text, w * 0.82);
  const lineHeight = fontSize * lineHeightMult;
  const totalH = lines.length * lineHeight;
  const cx = (s.posX != null ? s.posX : 0.5) * w;
  const cy = (s.posY != null ? s.posY : anchorDefaultY(s.anchor)) * h;
  const startY = cy - totalH / 2 + fontSize;

  if (s.effect === "pixelado") {{
    drawPixelatedText(ctx, w, h, lines, fontSpec, lineHeight, startY, s.color, s.intensity, cx, align, opacity, letterSpacing, wordSpacing);
    return;
  }}

  ctx.save();
  ctx.globalAlpha = opacity;
  if (s.effect === "blur") {{
    ctx.filter = `blur(${{s.intensity}}px)`;
  }}
  if (s.effect === "sombra") {{
    ctx.shadowColor = s.effectColor;
    ctx.shadowBlur = s.intensity * 2;
    ctx.shadowOffsetX = s.intensity * 0.4;
    ctx.shadowOffsetY = s.intensity * 0.4;
  }}
  ctx.lineWidth = Math.max(2, fontSize * 0.09);
  ctx.strokeStyle = s.effect === "contorno" ? s.effectColor : "rgba(0,0,0,0.7)";
  ctx.fillStyle = s.color;
  lines.forEach((line, i) => {{
    const y = startY + i * lineHeight;
    ctx.strokeText(line, cx, y);
    ctx.fillText(line, cx, y);
  }});
  ctx.restore();
}}

async function renderLine(index) {{
  const s = state[index];
  const canvas = document.getElementById(`canvas-${{index}}`);
  const w = Math.round(CANVAS_W * PREVIEW_SCALE);
  const h = Math.round(CANVAS_H * PREVIEW_SCALE);
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext("2d");
  const img = await loadImage(s.source);
  if (s.panX == null || s.panY == null) {{
    const pan = defaultPan(img.naturalWidth, img.naturalHeight, s.faceCy);
    s.panX = pan.panX; s.panY = pan.panY;
  }}
  ctx.clearRect(0, 0, w, h);
  drawCover(ctx, img, w, h, s.panX, s.panY);
  drawScrim(ctx, w, h, s.anchor);
  drawText(ctx, w, h, s.text, s);
}}

function selectCandidate(index, imageId, source, anchor, faceCy) {{
  const s = state[index];
  s.imageId = imageId; s.source = source; s.anchor = anchor; s.faceCy = faceCy;
  s.panX = null; s.panY = null; // se recalcula el encuadre por defecto para la nueva foto
  s.posY = anchorDefaultY(anchor);
  const posyEl = document.getElementById(`posy-${{index}}`);
  if (posyEl) posyEl.value = Math.round(s.posY * 100);
  document.querySelectorAll(`.thumb[data-line="${{index}}"]`).forEach(el => {{
    el.classList.toggle("selected", el.dataset.image === String(imageId));
  }});
  renderLine(index);
}}

const NUMERIC_STYLE_FIELDS = ["intensity", "fontSize", "opacity", "letterSpacing", "wordSpacing", "lineHeightMult"];

function updateStyle(index, field, value) {{
  state[index][field] = NUMERIC_STYLE_FIELDS.includes(field) ? Number(value) : value;
  document.getElementById(`effect-color-${{index}}`).style.display =
    state[index].effect === "sombra" || state[index].effect === "contorno" ? "block" : "none";
  document.getElementById(`intensity-${{index}}`).style.display =
    state[index].effect === "blur" || state[index].effect === "sombra" || state[index].effect === "pixelado" ? "block" : "none";
  renderLine(index);
}}

function updateText(index, value) {{
  state[index].text = value;
  renderLine(index);
}}

function updatePosition(index, axis, value) {{
  state[index][axis] = Number(value) / 100;
  renderLine(index);
}}

function setAlign(index, align) {{
  state[index].align = align;
  document.querySelectorAll(`.align-group[data-line="${{index}}"] button`).forEach(el => {{
    el.classList.toggle("active", el.dataset.align === align);
  }});
  renderLine(index);
}}

function initDrag(index) {{
  const canvas = document.getElementById(`canvas-${{index}}`);
  let dragging = false;

  function setFromEvent(e) {{
    const rect = canvas.getBoundingClientRect();
    const point = e.touches ? e.touches[0] : e;
    const x = Math.min(1, Math.max(0, (point.clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (point.clientY - rect.top) / rect.height));
    state[index].panX = x;
    state[index].panY = y;
    renderLine(index);
  }}

  canvas.addEventListener("mousedown", e => {{ dragging = true; setFromEvent(e); }});
  window.addEventListener("mousemove", e => {{ if (dragging) setFromEvent(e); }});
  window.addEventListener("mouseup", () => {{ dragging = false; }});
  canvas.addEventListener("touchstart", e => {{ dragging = true; setFromEvent(e); e.preventDefault(); }}, {{ passive: false }});
  canvas.addEventListener("touchmove", e => {{ if (dragging) {{ setFromEvent(e); e.preventDefault(); }} }}, {{ passive: false }});
  canvas.addEventListener("touchend", () => {{ dragging = false; }});
}}

async function downloadLine(index) {{
  const s = state[index];
  const canvas = document.createElement("canvas");
  canvas.width = CANVAS_W; canvas.height = CANVAS_H;
  const ctx = canvas.getContext("2d");
  const img = await loadImage(s.source);
  drawCover(ctx, img, CANVAS_W, CANVAS_H, s.panX, s.panY);
  drawScrim(ctx, CANVAS_W, CANVAS_H, s.anchor);
  drawText(ctx, CANVAS_W, CANVAS_H, s.text, s);
  const a = document.createElement("a");
  a.download = `${{String(index + 1).padStart(3, "0")}}.png`;
  a.href = canvas.toDataURL("image/png");
  a.click();
}}

function copySelection() {{
  const out = {{}};
  for (const [index, s] of Object.entries(state)) {{
    out[index] = {{
      text: s.text, image_id: s.imageId, font: s.font, color: s.color,
      effect: s.effect, effect_color: s.effectColor, intensity: s.intensity,
      pos_x: s.posX, pos_y: s.posY, align: s.align,
      font_size: s.fontSize, opacity: s.opacity,
      letter_spacing: s.letterSpacing, word_spacing: s.wordSpacing, line_height: s.lineHeightMult,
      image_pan_x: s.panX, image_pan_y: s.panY,
    }};
  }}
  const text = JSON.stringify(out, null, 2);
  navigator.clipboard.writeText(text).then(
    () => alert("Seleccion copiada al portapapeles:\\n" + text),
    () => prompt("Copia manualmente:", text)
  );
}}

DATA.forEach(line => {{
  const first = line.candidates[0];
  state[line.index] = {{
    text: line.line,
    imageId: first.image_id,
    source: first.source,
    faceCy: first.face_position ? first.face_position[1] : null,
    anchor: first.text_anchor,
    panX: null,
    panY: null,
    font: FONTS[0][0],
    color: "#ffffff",
    effect: "contorno",
    effectColor: "#000000",
    intensity: 8,
    fontSize: 0.075,
    opacity: 1,
    letterSpacing: 0,
    wordSpacing: 0,
    lineHeightMult: 1.25,
    posX: 0.5,
    posY: anchorDefaultY(first.text_anchor),
    align: "center",
  }};
  renderLine(line.index);
  initDrag(line.index);
}});

Promise.all(FONTS.map(f => document.fonts.load(`bold 40px ${{f[0]}}`).catch(() => {{}})))
  .then(() => DATA.forEach(line => renderLine(line.index)));
</script>
</body>
</html>
"""

LINE_TEMPLATE = """
<section class="line">
  <div class="preview">
    <canvas id="canvas-{index}"></canvas>
    <div class="drag-hint">Arrastr&aacute; la foto en la vista previa para reencuadrarla (el texto se mueve con los controles de posici&oacute;n)</div>
    <button onclick="downloadLine({index})">Descargar PNG</button>
  </div>
  <div class="panel">
    <h2>L&iacute;nea {index_h}</h2>
    <div class="candidates">
      {thumbs}
    </div>
    <label>Texto</label>
    <textarea class="text-edit" oninput="updateText({index}, this.value)">{text}</textarea>
    <div class="controls">
      <div>
        <label>Tipograf&iacute;a</label>
        <select onchange="updateStyle({index}, 'font', this.value)">
          {font_options}
        </select>
      </div>
      <div>
        <label>Color del texto</label>
        <input type="color" value="#ffffff" onchange="updateStyle({index}, 'color', this.value)">
      </div>
      <div>
        <label>Tama&ntilde;o del texto</label>
        <input type="range" min="2" max="16" step="0.5" value="7.5" onchange="updateStyle({index}, 'fontSize', this.value / 100)">
      </div>
      <div>
        <label>Transparencia</label>
        <input type="range" min="0" max="100" value="100" onchange="updateStyle({index}, 'opacity', this.value / 100)">
      </div>
      <div>
        <label>Efecto</label>
        <select onchange="updateStyle({index}, 'effect', this.value)">
          <option value="contorno">Contorno</option>
          <option value="sombra">Sombra (drop shadow)</option>
          <option value="blur">Blur</option>
          <option value="pixelado">Pixelado</option>
        </select>
      </div>
      <div id="effect-color-{index}" class="effect-color" style="display:block">
        <label>Color del contorno/sombra</label>
        <input type="color" value="#000000" onchange="updateStyle({index}, 'effectColor', this.value)">
      </div>
      <div id="intensity-{index}" class="intensity">
        <label>Intensidad</label>
        <input type="range" min="1" max="30" value="8" onchange="updateStyle({index}, 'intensity', this.value)">
      </div>
      <div>
        <label>Alineaci&oacute;n</label>
        <div class="align-group" data-line="{index}">
          <button type="button" data-align="left" onclick="setAlign({index}, 'left')">Izq.</button>
          <button type="button" data-align="center" class="active" onclick="setAlign({index}, 'center')">Centro</button>
          <button type="button" data-align="right" onclick="setAlign({index}, 'right')">Der.</button>
        </div>
      </div>
      <div>
        <label>Posici&oacute;n horizontal</label>
        <input id="posx-{index}" type="range" min="0" max="100" value="50" onchange="updatePosition({index}, 'posX', this.value)">
      </div>
      <div>
        <label>Posici&oacute;n vertical</label>
        <input id="posy-{index}" type="range" min="0" max="100" value="{posy_default}" onchange="updatePosition({index}, 'posY', this.value)">
      </div>
      <div>
        <label>Espacio entre letras</label>
        <input type="range" min="0" max="3" step="0.1" value="0" onchange="updateStyle({index}, 'letterSpacing', this.value / 100)">
      </div>
      <div>
        <label>Espacio entre palabras</label>
        <input type="range" min="0" max="6" step="0.2" value="0" onchange="updateStyle({index}, 'wordSpacing', this.value / 100)">
      </div>
      <div>
        <label>Espacio entre l&iacute;neas</label>
        <input type="range" min="0.8" max="2.5" step="0.05" value="1.25" onchange="updateStyle({index}, 'lineHeightMult', this.value)">
      </div>
    </div>
  </div>
</section>
"""

THUMB_TEMPLATE = """
<div class="thumb{selected_class}" data-line="{index}" data-image="{image_id}"
     onclick="selectCandidate({index}, {image_id}, '{source}', '{anchor}', {face_cy})">
  <img src="{composed}" alt="candidato {image_id}">
  <div class="meta">{image_id} &middot; {relation} &middot; conf {confidence}</div>
</div>
"""


def write_review_html(output_dir, results, format_name):
    canvas_w, canvas_h = FORMATS[format_name]

    lines_html = []
    for result in results:
        thumbs = "".join(
            THUMB_TEMPLATE.format(
                index=result["index"],
                image_id=c["image_id"],
                composed=c["composed"],
                source=c["source"],
                anchor=c["text_anchor"],
                face_cy=json.dumps(c["face_position"][1] if c.get("face_position") else None),
                relation=html.escape(c["relation"]),
                confidence=c["confidence"],
                selected_class=" selected" if i == 0 else "",
            )
            for i, c in enumerate(result["candidates"])
        )
        font_options = "".join(
            f'<option value="{html.escape(value)}">{html.escape(label)}</option>' for value, label in FONTS
        )
        first_anchor = result["candidates"][0]["text_anchor"]
        posy_default = round((BAND_FRAC / 2 if first_anchor == "top" else 1 - BAND_FRAC / 2) * 100)
        lines_html.append(
            LINE_TEMPLATE.format(
                index=result["index"],
                index_h=result["index"] + 1,
                text=html.escape(result["line"]),
                thumbs=thumbs,
                font_options=font_options,
                posy_default=posy_default,
            )
        )

    data_json = json.dumps(
        [
            {
                "index": r["index"],
                "line": r["line"],
                "candidates": [
                    {
                        "image_id": c["image_id"],
                        "source": c["source"],
                        "text_anchor": c["text_anchor"],
                        "face_position": c.get("face_position"),
                    }
                    for c in r["candidates"]
                ],
            }
            for r in results
        ],
        ensure_ascii=False,
    )
    html_out = TEMPLATE.format(
        lines="".join(lines_html),
        data_json=data_json,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        band_frac=BAND_FRAC,
        fonts_json=json.dumps(list(FONTS), ensure_ascii=False),
    )
    Path(output_dir, "review.html").write_text(html_out, encoding="utf-8")
