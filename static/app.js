// app.js - Interfaz web vanilla para creador-contenido

let currentJobId = null;
let statusPollingInterval = null;

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
