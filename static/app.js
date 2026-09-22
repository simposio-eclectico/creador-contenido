// app.js - Interfaz web vanilla para creador-contenido

// --------------------------------------------------------------------------
// Manejo de pestañas (tabs)
// --------------------------------------------------------------------------

let currentTab = "composition";
let currentJobId = null;
let statusPollingInterval = null;
let currentVideoJobId = null;
let videoPollingInterval = null;

function switchTab(tabName) {
  currentTab = tabName;

  // Oculta todos los tabs
  document.querySelectorAll(".tab-content").forEach(tab => {
    tab.classList.add("hidden");
  });

  // Muestra el tab seleccionado
  document.getElementById(`tab-${tabName}`).classList.remove("hidden");

  // Actualiza botones
  document.querySelectorAll(".tab-button").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });
}

// Event listeners para botones de tabs
document.querySelectorAll(".tab-button").forEach(btn => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

const formSection = document.getElementById("form-section");
const statusSection = document.getElementById("status-section");
const submitForm = document.getElementById("submit-form");
const statusBadge = document.getElementById("status-badge");
const statusStage = document.getElementById("status-stage");
const logElement = document.getElementById("log");
const resultArea = document.getElementById("result-area");
const errorArea = document.getElementById("error-area");
const reviewLink = document.getElementById("review-link");
const errorText = document.getElementById("error-text");
const btnReset = document.getElementById("btn-reset");

// Elementos para manejo de archivo
const lyricsFileInput = document.getElementById("lyrics-file");
const lyricsTextarea = document.getElementById("lyrics");

// Maneja la selección de archivo de letra
lyricsFileInput.addEventListener("change", async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  try {
    const text = await file.text();
    lyricsTextarea.value = text;
    // Visual feedback
    lyricsTextarea.style.borderColor = "var(--accent)";
    setTimeout(() => {
      lyricsTextarea.style.borderColor = "";
    }, 1500);
  } catch (error) {
    alert(`Error al leer el archivo: ${error.message}`);
    lyricsFileInput.value = "";
  }
});

// Limpia el input file si el usuario edita el textarea
lyricsTextarea.addEventListener("input", () => {
  if (lyricsFileInput.value) {
    lyricsFileInput.value = "";
  }
});

// --------------------------------------------------------------------------
// Modo de selección (automático / manual)
// --------------------------------------------------------------------------

const selectionModeRadios = document.querySelectorAll('input[name="selection_mode"]');
const topKFieldset = document.getElementById("top-k-fieldset");

function updateTopKAvailability() {
  const mode = document.querySelector('input[name="selection_mode"]:checked')?.value;
  const isManual = mode === "manual";
  topKFieldset.classList.toggle("disabled", isManual);
  document.getElementById("top-k").disabled = isManual;
}

selectionModeRadios.forEach((radio) => radio.addEventListener("change", updateTopKAvailability));
updateTopKAvailability();

// --------------------------------------------------------------------------
// Selector visual de carpetas
// --------------------------------------------------------------------------

const folderInput = document.getElementById("folder");
const btnBrowseFolder = document.getElementById("btn-browse-folder");
const browserModal = document.getElementById("folder-browser-modal");
const btnBrowseClose = document.getElementById("btn-browse-close");
const btnBrowseUp = document.getElementById("btn-browse-up");
const btnBrowseSelect = document.getElementById("btn-browse-select");
const browseCurrentPath = document.getElementById("browse-current-path");
const browseMetadataBadge = document.getElementById("browse-metadata-badge");
const browseDirList = document.getElementById("browse-dir-list");
const browseError = document.getElementById("browse-error");

let browserCurrentPath = null;
let browserParentPath = null;

async function loadBrowseDir(path, { fallbackToHome = false } = {}) {
  browseError.classList.add("hidden");

  const url = path ? `/api/browse?path=${encodeURIComponent(path)}` : "/api/browse";
  try {
    const response = await fetch(url);
    const data = await response.json();

    if (!response.ok) {
      if (fallbackToHome) {
        return loadBrowseDir(null);
      }
      browseError.textContent = data.error || "No se pudo abrir la carpeta";
      browseError.classList.remove("hidden");
      return;
    }

    browserCurrentPath = data.current;
    browserParentPath = data.parent;
    browseCurrentPath.textContent = data.current;
    browseMetadataBadge.classList.toggle("hidden", !data.has_metadata);
    btnBrowseUp.disabled = !data.parent;

    browseDirList.innerHTML = "";

    if (data.dirs.length === 0) {
      const li = document.createElement("li");
      li.className = "empty-message";
      li.textContent = "(sin subcarpetas)";
      browseDirList.appendChild(li);
    } else {
      for (const dir of data.dirs) {
        const li = document.createElement("li");
        li.innerHTML = `
          <span class="dir-icon">📁</span>
          <span class="dir-name">${escapeHtml(dir.name)}</span>
          ${dir.has_metadata ? '<span class="metadata-badge">metadata.json</span>' : ""}
        `;
        li.addEventListener("click", () => loadBrowseDir(dir.path));
        browseDirList.appendChild(li);
      }
    }
  } catch (error) {
    if (fallbackToHome) {
      return loadBrowseDir(null);
    }
    browseError.textContent = `Error de red: ${error.message}`;
    browseError.classList.remove("hidden");
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function openBrowser() {
  browserModal.classList.remove("hidden");
  // Arranca desde el valor actual del input si parece una ruta válida, si no desde home
  const startPath = folderInput.value.trim() || null;
  loadBrowseDir(startPath, { fallbackToHome: true });
}

function closeBrowser() {
  browserModal.classList.add("hidden");
}

btnBrowseFolder.addEventListener("click", openBrowser);
btnBrowseClose.addEventListener("click", closeBrowser);

btnBrowseUp.addEventListener("click", () => {
  if (browserParentPath) {
    loadBrowseDir(browserParentPath);
  }
});

btnBrowseSelect.addEventListener("click", () => {
  if (browserCurrentPath) {
    folderInput.value = browserCurrentPath;
  }
  closeBrowser();
});

browserModal.addEventListener("click", (e) => {
  if (e.target === browserModal) {
    closeBrowser();
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !browserModal.classList.contains("hidden")) {
    closeBrowser();
  }
});

submitForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  // Recoge datos del formulario
  const formData = new FormData(submitForm);
  const payload = {
    folder: formData.get("folder"),
    lyrics_text: lyricsTextarea.value.trim(),
    format: formData.get("format"),
    selection_mode: formData.get("selection_mode") || "auto",
    top_k: parseInt(formData.get("top_k")) || 5,
    device: formData.get("device"),
    cluster_eps: parseFloat(formData.get("cluster_eps")) || 0.08,
    no_faces: formData.get("no_faces") ? true : false,
    favorites_path: formData.get("favorites_path") || null,
    generate_output: formData.get("generate_output") || null,
    main_output: formData.get("main_output") || null,
  };

  // Validación local
  if (!payload.lyrics_text) {
    alert("Debes escribir o cargar una letra.");
    return;
  }

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json();
      alert(`Error: ${error.error || "No se pudo crear el job"}`);
      return;
    }

    const result = await response.json();
    currentJobId = result.job_id;

    // Muestra la sección de estado
    formSection.classList.add("hidden");
    statusSection.classList.remove("hidden");
    logElement.textContent = "";
    resultArea.classList.add("hidden");
    errorArea.classList.add("hidden");
    btnReset.classList.add("hidden");

    // Inicia polling
    pollStatus();
    statusPollingInterval = setInterval(pollStatus, 1500);
  } catch (error) {
    alert(`Error al enviar: ${error.message}`);
  }
});

async function pollStatus() {
  if (!currentJobId) return;

  try {
    const response = await fetch(`/api/jobs/${currentJobId}`);
    if (!response.ok) {
      console.error("Error al consultar estado");
      return;
    }

    const job = await response.json();

    // Actualiza badge
    statusBadge.textContent = formatStatus(job.status);
    statusBadge.className = `status-badge ${job.status}`;

    // Actualiza stage
    statusStage.textContent = job.stage || "";

    // Actualiza log
    logElement.textContent = job.log_tail || "";
    logElement.scrollTop = logElement.scrollHeight;

    // Maneja completación o error
    if (job.status === "done") {
      clearInterval(statusPollingInterval);
      resultArea.classList.remove("hidden");
      reviewLink.href = job.review_url;
      btnReset.classList.remove("hidden");
    } else if (job.status === "error") {
      clearInterval(statusPollingInterval);
      errorArea.classList.remove("hidden");
      errorText.textContent = job.error || "Error desconocido";
      btnReset.classList.remove("hidden");
    }
  } catch (error) {
    console.error("Error polling:", error);
  }
}

// --------------------------------------------------------------------------
// Manejo de procesamiento de video
// --------------------------------------------------------------------------

const videoForm = document.getElementById("video-form");
const videoInput = document.getElementById("video-input");
const videoFormSection = document.getElementById("video-form-section");
const videoStatusSection = document.getElementById("video-status-section");
const videoBadge = document.getElementById("video-status-badge");
const videoStage = document.getElementById("video-status-stage");
const videoLog = document.getElementById("video-log");
const videoResultArea = document.getElementById("video-result-area");
const videoErrorArea = document.getElementById("video-error-area");
const videoErrorText = document.getElementById("video-error-text");
const btnVideoReset = document.getElementById("btn-video-reset");
const btnUseVideoOutput = document.getElementById("btn-use-video-output");
let lastVideoOutput = null;

btnUseVideoOutput.addEventListener("click", () => {
  if (lastVideoOutput) {
    folderInput.value = lastVideoOutput;
    switchTab("composition");
    // Scroll to folder field
    folderInput.scrollIntoView({ behavior: "smooth" });
  }
});

videoForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const file = videoInput.files?.[0];
  if (!file) {
    alert("Selecciona un archivo de video");
    return;
  }

  const formData = new FormData();
  formData.append("video", file);

  try {
    const response = await fetch("/api/upload-video", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      alert(`Error: ${error.error || "No se pudo enviar el video"}`);
      return;
    }

    const result = await response.json();
    currentVideoJobId = result.job_id;

    videoFormSection.classList.add("hidden");
    videoStatusSection.classList.remove("hidden");
    videoLog.textContent = "";
    videoResultArea.classList.add("hidden");
    videoErrorArea.classList.add("hidden");
    btnVideoReset.classList.add("hidden");

    pollVideoStatus();
    videoPollingInterval = setInterval(pollVideoStatus, 1500);
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
});

async function pollVideoStatus() {
  if (!currentVideoJobId) return;

  try {
    const response = await fetch(`/api/video-jobs/${currentVideoJobId}`);
    if (!response.ok) {
      console.error("Error al consultar estado de video");
      return;
    }

    const job = await response.json();

    videoBadge.textContent = formatVideoStatus(job.status);
    videoBadge.className = `status-badge ${job.status}`;

    videoStage.textContent = job.stage || "";
    videoLog.textContent = job.log_tail || "";
    videoLog.scrollTop = videoLog.scrollHeight;

    if (job.status === "done") {
      clearInterval(videoPollingInterval);
      videoResultArea.classList.remove("hidden");
      btnVideoReset.classList.remove("hidden");

      if (job.video_output) {
        lastVideoOutput = job.video_output;
      }
    } else if (job.status === "error") {
      clearInterval(videoPollingInterval);
      videoErrorArea.classList.remove("hidden");
      videoErrorText.textContent = job.error || "Error desconocido";
      btnVideoReset.classList.remove("hidden");
    }
  } catch (error) {
    console.error("Error polling video:", error);
  }
}

function formatVideoStatus(status) {
  const labels = {
    pending: "⏳ Pendiente",
    processing: "🎬 Procesando video",
    done: "✅ Listo",
    error: "❌ Error",
  };
  return labels[status] || status;
}

btnVideoReset.addEventListener("click", () => {
  currentVideoJobId = null;
  if (videoPollingInterval) {
    clearInterval(videoPollingInterval);
  }
  videoStatusSection.classList.add("hidden");
  videoFormSection.classList.remove("hidden");
  videoForm.reset();
  videoLog.textContent = "";
  videoResultArea.classList.add("hidden");
  videoErrorArea.classList.add("hidden");
  btnVideoReset.classList.add("hidden");
});

// --------------------------------------------------------------------------
// Manejo de extraccion de reels (Tab 3)
// --------------------------------------------------------------------------

let currentReelJobId = null;
let reelPollingInterval = null;

const reelForm = document.getElementById("reel-form");
const reelVideoInput = document.getElementById("reel-video-input");
const reelFormSection = document.getElementById("reel-form-section");
const reelStatusSection = document.getElementById("reel-status-section");
const reelBadge = document.getElementById("reel-status-badge");
const reelStage = document.getElementById("reel-status-stage");
const reelLog = document.getElementById("reel-log");
const reelReviewArea = document.getElementById("reel-review-area");
const reelReviewList = document.getElementById("reel-review-list");
const btnConfirmSubtitles = document.getElementById("btn-confirm-subtitles");
const subStyleFontColor = document.getElementById("sub-style-font-color");
const subStyleFontOpacity = document.getElementById("sub-style-font-opacity");
const subStyleBackgroundEnabled = document.getElementById("sub-style-background-enabled");
const subStyleBackgroundColor = document.getElementById("sub-style-background-color");
const subStyleBackgroundOpacity = document.getElementById("sub-style-background-opacity");
const subStyleOutlineEnabled = document.getElementById("sub-style-outline-enabled");
const subStyleOutlineColor = document.getElementById("sub-style-outline-color");
const subStyleOutlineWidth = document.getElementById("sub-style-outline-width");
const reelResultArea = document.getElementById("reel-result-area");
const reelGallery = document.getElementById("reel-gallery");
const reelErrorArea = document.getElementById("reel-error-area");
const reelErrorText = document.getElementById("reel-error-text");
const btnReelReset = document.getElementById("btn-reel-reset");

const reelDurationInput = document.getElementById("reel-duration");
const reelDurationLabel = document.getElementById("reel-duration-label");
const reelAudioWeightInput = document.getElementById("reel-audio-weight");
const reelWeightLabel = document.getElementById("reel-weight-label");

reelDurationInput.addEventListener("input", () => {
  reelDurationLabel.textContent = `${reelDurationInput.value}s`;
});

function audioWeightPresetLabel(value) {
  if (value < 33) return "Solo visual";
  if (value > 66) return "Priorizar audio";
  return "Balanceado";
}

reelAudioWeightInput.addEventListener("input", () => {
  reelWeightLabel.textContent = audioWeightPresetLabel(parseInt(reelAudioWeightInput.value, 10));
});

// --------------------------------------------------------------------------
// Opciones de fadeout (Tab 3)
// --------------------------------------------------------------------------

const reelFadeEnabled = document.getElementById("reel-fade-enabled");
const reelFadeOptions = document.getElementById("reel-fade-options");
const reelFadeDuration = document.getElementById("reel-fade-duration");
const reelFadeDurationLabel = document.getElementById("reel-fade-duration-label");
const reelFadeImageField = document.getElementById("reel-fade-image-field");
const reelFadeTargetRadios = document.querySelectorAll('input[name="fade_target"]');

reelFadeEnabled.addEventListener("change", () => {
  reelFadeOptions.classList.toggle("hidden", !reelFadeEnabled.checked);
});

reelFadeDuration.addEventListener("input", () => {
  reelFadeDurationLabel.textContent = `${reelFadeDuration.value}s`;
});

function updateFadeImageFieldVisibility() {
  const target = document.querySelector('input[name="fade_target"]:checked')?.value;
  reelFadeImageField.classList.toggle("hidden", target !== "image");
}

reelFadeTargetRadios.forEach((radio) => radio.addEventListener("change", updateFadeImageFieldVisibility));

reelForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const file = reelVideoInput.files?.[0];
  if (!file) {
    alert("Selecciona un archivo de video");
    return;
  }

  const fadeTarget = document.querySelector('input[name="fade_target"]:checked')?.value || "black";
  if (reelFadeEnabled.checked && fadeTarget === "image" && !document.getElementById("reel-fade-image").files?.[0]) {
    alert("Selecciona una imagen para el fundido, o elige 'Fundido a negro'");
    return;
  }

  const formData = new FormData();
  formData.append("video", file);
  formData.append("duration", reelDurationInput.value);
  formData.append("count", document.getElementById("reel-count").value);
  formData.append("audio_weight", (parseInt(reelAudioWeightInput.value, 10) / 100).toFixed(2));
  formData.append("format", document.getElementById("reel-format").value);
  formData.append("subtitles", document.getElementById("reel-subtitles").checked ? "1" : "");
  formData.append("whisper_model", document.getElementById("reel-whisper-model").value);
  formData.append("subtitle_font", document.getElementById("reel-subtitle-font").value);
  formData.append("language", document.getElementById("reel-language").value);
  formData.append("fade_out", reelFadeEnabled.checked ? reelFadeDuration.value : "0");
  formData.append("fade_target", fadeTarget);
  if (reelFadeEnabled.checked && fadeTarget === "image") {
    formData.append("fade_image", document.getElementById("reel-fade-image").files[0]);
    formData.append("fade_image_fit", document.getElementById("reel-fade-image-fit").value);
    formData.append("fade_background_color", document.getElementById("reel-fade-background-color").value);
  }

  try {
    const response = await fetch("/api/upload-reel-video", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      alert(`Error: ${error.error || "No se pudo enviar el video"}`);
      return;
    }

    const result = await response.json();
    currentReelJobId = result.job_id;

    reelFormSection.classList.add("hidden");
    reelStatusSection.classList.remove("hidden");
    reelLog.textContent = "";
    reelReviewArea.classList.add("hidden");
    reelReviewList.innerHTML = "";
    reelResultArea.classList.add("hidden");
    reelGallery.innerHTML = "";
    reelErrorArea.classList.add("hidden");
    btnReelReset.classList.add("hidden");

    pollReelStatus();
    reelPollingInterval = setInterval(pollReelStatus, 1500);
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
});

async function pollReelStatus() {
  if (!currentReelJobId) return;

  try {
    const response = await fetch(`/api/reel-jobs/${currentReelJobId}`);
    if (!response.ok) {
      console.error("Error al consultar estado de reels");
      return;
    }

    const job = await response.json();

    reelBadge.textContent = formatReelStatus(job.status);
    reelBadge.className = `status-badge ${job.status}`;

    reelStage.textContent = job.stage || "";
    reelLog.textContent = job.log_tail || "";
    reelLog.scrollTop = reelLog.scrollHeight;

    if (job.status === "awaiting_review") {
      clearInterval(reelPollingInterval);
      reelReviewArea.classList.remove("hidden");
      renderReelReview(job.reels || []);
    } else if (job.status === "done") {
      clearInterval(reelPollingInterval);
      reelReviewArea.classList.add("hidden");
      reelResultArea.classList.remove("hidden");
      btnReelReset.classList.remove("hidden");
      renderReelGallery(job.reels || []);
    } else if (job.status === "error") {
      clearInterval(reelPollingInterval);
      reelErrorArea.classList.remove("hidden");
      reelErrorText.textContent = job.error || "Error desconocido";
      btnReelReset.classList.remove("hidden");
    }
  } catch (error) {
    console.error("Error polling reels:", error);
  }
}

function createSegmentRow(container, idx, start, end, text, card, btnAddSegment = null) {
  const row = document.createElement("div");
  row.className = "segment-row-editable";

  // Contenedor para tiempos (en la misma línea)
  const timeContainer = document.createElement("div");
  timeContainer.className = "segment-times-container";

  const startInput = document.createElement("input");
  startInput.type = "number";
  startInput.step = "0.1";
  startInput.min = "0";
  startInput.value = start.toFixed(2);
  startInput.className = "segment-time-input";
  startInput.dataset.segIndex = idx;
  startInput.dataset.timeField = "start";
  startInput.placeholder = "0.0s";
  timeContainer.appendChild(startInput);

  const endInput = document.createElement("input");
  endInput.type = "number";
  endInput.step = "0.1";
  endInput.min = "0";
  endInput.value = end.toFixed(2);
  endInput.className = "segment-time-input";
  endInput.dataset.segIndex = idx;
  endInput.dataset.timeField = "end";
  endInput.placeholder = "1.0s";
  timeContainer.appendChild(endInput);

  row.appendChild(timeContainer);

  // Texto
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.className = "segment-text-input";
  textarea.dataset.segIndex = idx;
  textarea.placeholder = "Escribe el texto del subtítulo...";
  textarea.addEventListener("input", () => updateSubtitlePreview(card));
  row.appendChild(textarea);

  // Botón eliminar
  const btnDelete = document.createElement("button");
  btnDelete.className = "btn-delete-segment";
  btnDelete.textContent = "✕";
  btnDelete.type = "button";
  btnDelete.addEventListener("click", () => {
    row.remove();
    updateSubtitlePreview(card);
  });
  row.appendChild(btnDelete);

  if (btnAddSegment) {
    container.insertBefore(row, btnAddSegment);
  } else {
    container.appendChild(row);
  }
}

function formatVideoTime(seconds) {
  if (!isFinite(seconds) || seconds < 0) seconds = 0;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// Agrega un indicador "mm:ss / mm:ss" sobre el video (container debe tener
// position:relative). Los controles nativos (video.controls=true) ya
// permiten reproducir desde el inicio o hacer seek a cualquier punto de la
// barra; esto solo agrega un indicador de tiempo más visible/legible.
function attachTimeDisplay(video, container) {
  const timeDisplay = document.createElement("div");
  timeDisplay.className = "video-time-display";
  timeDisplay.textContent = "0:00 / 0:00";
  container.appendChild(timeDisplay);

  const update = () => {
    timeDisplay.textContent = `${formatVideoTime(video.currentTime)} / ${formatVideoTime(video.duration)}`;
  };
  video.addEventListener("timeupdate", update);
  video.addEventListener("loadedmetadata", update);
  video.addEventListener("seeking", update);
  return timeDisplay;
}

function renderReelReview(reels) {
  reelReviewList.innerHTML = "";
  reels.forEach((r) => {
    const card = document.createElement("div");
    card.className = "reel-review-card";
    card.dataset.reelId = r.id;

    // Video player con overlay de subtítulos
    const playerContainer = document.createElement("div");
    playerContainer.className = "reel-player-container";

    const video = document.createElement("video");
    video.src = r.clip_url;
    video.controls = true;
    video.addEventListener("timeupdate", () => {
      updateSubtitlePreview(card, video.currentTime);
    });
    playerContainer.appendChild(video);
    attachTimeDisplay(video, playerContainer);

    const subtitleOverlay = document.createElement("div");
    subtitleOverlay.className = "subtitle-overlay";
    playerContainer.appendChild(subtitleOverlay);
    card.appendChild(playerContainer);

    // Editor de segmentos
    const editor = document.createElement("div");
    editor.className = "segments-editor";

    const title = document.createElement("h4");
    title.textContent = `Reel ${r.id} — ${r.start.toFixed(1)}s a ${r.end.toFixed(1)}s`;
    editor.appendChild(title);

    const segments = r.segments || [];
    const segmentsContainer = document.createElement("div");
    segmentsContainer.className = "segments-list";

    // Renderizar segmentos detectados
    segments.forEach((seg, idx) => {
      createSegmentRow(segmentsContainer, idx, seg.start, seg.end, seg.text, card);
    });

    // Mostrar mensaje si no hay segmentos detectados
    if (segments.length === 0) {
      const empty = document.createElement("p");
      empty.className = "no-segments";
      empty.textContent = "No se detectó texto hablado en este reel. Puedes agregar subtítulos manualmente:";
      segmentsContainer.appendChild(empty);
    }

    // Botón para agregar nueva línea (siempre disponible)
    const btnAddSegment = document.createElement("button");
    btnAddSegment.className = "btn-add-segment";
    btnAddSegment.textContent = "+ Agregar línea";
    btnAddSegment.type = "button";
    btnAddSegment.addEventListener("click", () => {
      const newIdx = segmentsContainer.querySelectorAll(".segment-row-editable").length;
      createSegmentRow(segmentsContainer, newIdx, 0, 1, "", card, btnAddSegment);
      updateSubtitlePreview(card);
    });
    segmentsContainer.appendChild(btnAddSegment);

    editor.appendChild(segmentsContainer);
    card.appendChild(editor);
    reelReviewList.appendChild(card);
  });
}

// Lee los controles de estilo (color/transparencia/fondo/borde) y devuelve
// un objeto usado tanto para la vista previa en vivo (CSS) como para el
// payload enviado a /confirm-subtitles (que lo reenvia a burn_subs.py).
function getSubtitleStyle() {
  return {
    font_color: subStyleFontColor.value,
    font_opacity: parseInt(subStyleFontOpacity.value, 10) / 100,
    background_enabled: subStyleBackgroundEnabled.checked,
    background_color: subStyleBackgroundColor.value,
    background_opacity: parseInt(subStyleBackgroundOpacity.value, 10) / 100,
    outline_enabled: subStyleOutlineEnabled.checked,
    outline_color: subStyleOutlineColor.value,
    outline_width: parseInt(subStyleOutlineWidth.value, 10),
  };
}

function applySubtitleStyleToElement(el, style) {
  el.style.color = style.font_color;
  el.style.opacity = style.font_opacity;
  el.style.backgroundColor = style.background_enabled
    ? hexToRgba(style.background_color, style.background_opacity)
    : "transparent";
  el.style.textShadow = style.outline_enabled
    ? buildOutlineShadow(style.outline_color, style.outline_width)
    : "none";
}

function hexToRgba(hex, opacity) {
  const h = hex.replace("#", "");
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}

// Simula un contorno (drawtext borderw/bordercolor) apilando text-shadow
// en 8 direcciones, ya que CSS no tiene un equivalente directo a 1:1.
function buildOutlineShadow(color, width) {
  const offsets = [[-1,-1],[1,-1],[-1,1],[1,1],[0,-1],[0,1],[-1,0],[1,0]];
  return offsets.map(([x, y]) => `${x * width}px ${y * width}px 0 ${color}`).join(", ");
}

function updateAllSubtitlePreviewStyles() {
  const style = getSubtitleStyle();
  document.querySelectorAll(".reel-review-card").forEach((card) => {
    card.querySelectorAll(".subtitle-text").forEach((el) => applySubtitleStyleToElement(el, style));
  });
}

[
  subStyleFontColor, subStyleFontOpacity,
  subStyleBackgroundEnabled, subStyleBackgroundColor, subStyleBackgroundOpacity,
  subStyleOutlineEnabled, subStyleOutlineColor, subStyleOutlineWidth,
].forEach((el) => {
  el.addEventListener("input", updateAllSubtitlePreviewStyles);
  el.addEventListener("change", updateAllSubtitlePreviewStyles);
});

function updateSubtitlePreview(card, currentTime = 0) {
  const overlay = card.querySelector(".subtitle-overlay");
  overlay.innerHTML = "";

  const style = getSubtitleStyle();
  const rows = card.querySelectorAll(".segment-row-editable");
  rows.forEach((row) => {
    const startInput = row.querySelector("input[data-time-field='start']");
    const endInput = row.querySelector("input[data-time-field='end']");
    const textarea = row.querySelector(".segment-text-input");

    const start = parseFloat(startInput.value) || 0;
    const end = parseFloat(endInput.value) || 0;
    const text = textarea.value.trim();

    // Mostrar subtítulo si está en el rango de tiempo actual
    if (currentTime >= start && currentTime <= end && text) {
      const subtitle = document.createElement("div");
      subtitle.className = "subtitle-text";
      subtitle.textContent = text;
      applySubtitleStyleToElement(subtitle, style);
      overlay.appendChild(subtitle);
    }
  });
}

btnConfirmSubtitles.addEventListener("click", async () => {
  if (!currentReelJobId) return;

  const reelsPayload = [];
  reelReviewList.querySelectorAll(".reel-review-card").forEach((card) => {
    const reelId = parseInt(card.dataset.reelId, 10);
    const segments = [];
    card.querySelectorAll(".segment-row-editable").forEach((row) => {
      const startInput = row.querySelector("input[data-time-field='start']");
      const endInput = row.querySelector("input[data-time-field='end']");
      const textarea = row.querySelector(".segment-text-input");
      const text = textarea.value.trim();

      if (text) {  // Solo incluir segmentos que tengan texto
        segments.push({
          start: parseFloat(startInput.value) || 0,
          end: parseFloat(endInput.value) || 0,
          text: text,
        });
      }
    });
    reelsPayload.push({ id: reelId, segments });
  });

  btnConfirmSubtitles.disabled = true;
  btnConfirmSubtitles.textContent = "Quemando subtítulos...";

  try {
    const response = await fetch(`/api/reel-jobs/${currentReelJobId}/confirm-subtitles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reels: reelsPayload, subtitle_style: getSubtitleStyle() }),
    });

    if (!response.ok) {
      const error = await response.json();
      alert(`Error: ${error.error || "No se pudo confirmar"}`);
      btnConfirmSubtitles.disabled = false;
      btnConfirmSubtitles.textContent = "✓ Confirmar y quemar subtítulos →";
      return;
    }

    reelReviewArea.classList.add("hidden");
    pollReelStatus();
    reelPollingInterval = setInterval(pollReelStatus, 1500);
  } catch (error) {
    alert(`Error: ${error.message}`);
  } finally {
    btnConfirmSubtitles.disabled = false;
    btnConfirmSubtitles.textContent = "✓ Confirmar y quemar subtítulos →";
  }
});

function renderReelGallery(reels) {
  reelGallery.innerHTML = "";
  reels.forEach((r) => {
    const card = document.createElement("div");
    card.className = "reel-card";

    const playerContainer = document.createElement("div");
    playerContainer.className = "reel-card-player";

    const video = document.createElement("video");
    video.src = r.burned_clip_url || r.clip_url;
    video.controls = true;
    playerContainer.appendChild(video);
    attachTimeDisplay(video, playerContainer);
    card.appendChild(playerContainer);

    const meta = document.createElement("p");
    meta.textContent = `Reel ${r.id} — ${r.start.toFixed(1)}s a ${r.end.toFixed(1)}s (score ${r.score.toFixed(2)})`;
    card.appendChild(meta);

    const links = document.createElement("div");
    links.className = "reel-card-links";

    const clipLink = document.createElement("a");
    clipLink.href = r.clip_url;
    clipLink.download = "";
    clipLink.textContent = "⬇ Sin subtítulos";
    links.appendChild(clipLink);

    if (r.burned_clip_url) {
      const a = document.createElement("a");
      a.href = r.burned_clip_url;
      a.download = "";
      a.textContent = "⬇ Con subtítulos";
      links.appendChild(a);
    }
    if (r.srt_url) {
      const a = document.createElement("a");
      a.href = r.srt_url;
      a.download = "";
      a.textContent = "⬇ .srt";
      links.appendChild(a);
    }
    card.appendChild(links);

    reelGallery.appendChild(card);
  });
}

function formatReelStatus(status) {
  const labels = {
    pending: "⏳ Pendiente",
    processing: "🎬 Procesando",
    awaiting_review: "📝 Revisa los subtítulos",
    done: "✅ Listo",
    error: "❌ Error",
  };
  return labels[status] || status;
}

btnReelReset.addEventListener("click", () => {
  currentReelJobId = null;
  if (reelPollingInterval) {
    clearInterval(reelPollingInterval);
  }
  reelStatusSection.classList.add("hidden");
  reelFormSection.classList.remove("hidden");
  reelForm.reset();
  reelFadeOptions.classList.add("hidden");
  reelFadeImageField.classList.add("hidden");
  reelFadeDurationLabel.textContent = "3s";
  reelLog.textContent = "";
  reelReviewArea.classList.add("hidden");
  reelReviewList.innerHTML = "";
  reelResultArea.classList.add("hidden");
  reelGallery.innerHTML = "";
  reelErrorArea.classList.add("hidden");
  btnReelReset.classList.add("hidden");
});

btnReset.addEventListener("click", () => {
  currentJobId = null;
  if (statusPollingInterval) {
    clearInterval(statusPollingInterval);
  }
  statusSection.classList.add("hidden");
  formSection.classList.remove("hidden");
  submitForm.reset();
  logElement.textContent = "";
  resultArea.classList.add("hidden");
  errorArea.classList.add("hidden");
  btnReset.classList.add("hidden");
});

function formatStatus(status) {
  const labels = {
    pending: "⏳ Pendiente",
    running_generate: "🔄 Procesando fotos",
    running_main: "🔄 Asociando frases",
    done: "✅ Listo",
    error: "❌ Error",
  };
  return labels[status] || status;
}

// Focus en el log cuando hay actualizaciones
document.addEventListener("DOMContentLoaded", () => {
  // Auto-focus en el folder input
  document.getElementById("folder").focus();
});
