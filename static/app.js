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

submitForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  // Recoge datos del formulario
  const formData = new FormData(submitForm);
  const payload = {
    folder: formData.get("folder"),
    lyrics_text: formData.get("lyrics"),
    format: formData.get("format"),
    top_k: parseInt(formData.get("top_k")) || 5,
    device: formData.get("device"),
    cluster_eps: parseFloat(formData.get("cluster_eps")) || 0.08,
    no_faces: formData.get("no_faces") ? true : false,
    favorites_path: formData.get("favorites_path") || null,
    generate_output: formData.get("generate_output") || null,
    main_output: formData.get("main_output") || null,
  };

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
