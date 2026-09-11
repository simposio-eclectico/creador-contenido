(function () {
  "use strict";

  const DATA = window.METADATA || { source: "unknown", duration: 0, frames: [] };
  const STORAGE_KEY = `contact-sheet:${DATA.source}:${DATA.duration}`;

  const byId = new Map(DATA.frames.map((r) => [r.id, r]));

  let state = { favorites: new Set(), ratings: {}, pins: {} };
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (saved) {
      state.favorites = new Set(saved.favorites || []);
      state.ratings = saved.ratings || {};
      state.pins = saved.pins || {};
    }
  } catch (e) { /* ignore corrupt storage */ }

  function persist() {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        favorites: [...state.favorites],
        ratings: state.ratings,
        pins: state.pins,
      })
    );
    scheduleBackup();
  }

  // ---- Respaldo automatico en JSON (File System Access API) --------------
  const BACKUP_HANDLE_KEY = STORAGE_KEY + ":backup-handle";
  let backupHandle = null;
  let backupStatus = "sin-configurar"; // activo | sin-configurar | reconectar | no-soportado
  let backupTimer = null;

  function idbOpen() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open("contact-sheet-review", 1);
      req.onupgradeneeded = () => req.result.createObjectStore("handles");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  async function idbSet(key, value) {
    const db = await idbOpen();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("handles", "readwrite");
      tx.objectStore("handles").put(value, key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }
  async function idbGet(key) {
    const db = await idbOpen();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("handles", "readonly");
      const req = tx.objectStore("handles").get(key);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  function buildBackupPayload() {
    const favRecs = getFavoritesSorted();
    return {
      source: DATA.source,
      duration: DATA.duration,
      savedAt: new Date().toISOString(),
      favorites: favRecs.map((r) => r.id),
      ratings: state.ratings,
      pins: state.pins,
      frames: favRecs.map((r) => ({
        id: r.id,
        time: r.time,
        full: exportPathFor(r),
        thumb: r.thumb,
        rating: state.ratings[r.id] || null,
      })),
    };
  }

  function renderBackupStatus() {
    const el = document.getElementById("backup-status");
    if (!el) return;
    const map = {
      activo: "Respaldo automatico: activo",
      "sin-configurar": "Respaldo automatico: no configurado",
      reconectar: "Respaldo automatico: reconectar (boton de abajo)",
      "no-soportado": "Respaldo automatico no soportado; usa descarga manual",
    };
    el.textContent = map[backupStatus] || "";
  }

  async function initBackupHandle() {
    if (!("showSaveFilePicker" in window)) {
      backupStatus = "no-soportado";
      renderBackupStatus();
      return;
    }
    try {
      const stored = await idbGet(BACKUP_HANDLE_KEY);
      if (stored) {
        const perm = await stored.queryPermission({ mode: "readwrite" });
        backupHandle = stored;
        backupStatus = perm === "granted" ? "activo" : "reconectar";
      } else {
        backupStatus = "sin-configurar";
      }
    } catch (e) {
      backupStatus = "sin-configurar";
    }
    renderBackupStatus();
  }

  async function connectBackupFile() {
    try {
      let handle = backupHandle;
      if (handle) {
        const perm = await handle.requestPermission({ mode: "readwrite" });
        if (perm !== "granted") handle = null;
      }
      if (!handle) {
        handle = await window.showSaveFilePicker({
          suggestedName: `${DATA.source}.json`,
          types: [{ description: "JSON", accept: { "application/json": [".json"] } }],
        });
        await idbSet(BACKUP_HANDLE_KEY, handle);
      }
      backupHandle = handle;
      backupStatus = "activo";
      await writeBackupNow();
    } catch (e) {
      console.warn("No se pudo configurar el respaldo automatico.", e);
    }
    renderBackupStatus();
  }

  async function writeBackupNow() {
    if (!backupHandle) return;
    try {
      const writable = await backupHandle.createWritable();
      await writable.write(JSON.stringify(buildBackupPayload(), null, 2));
      await writable.close();
      backupStatus = "activo";
    } catch (e) {
      console.warn("Fallo al escribir el respaldo automatico.", e);
      backupStatus = "reconectar";
    }
    renderBackupStatus();
  }

  function scheduleBackup() {
    if (!backupHandle) return;
    clearTimeout(backupTimer);
    backupTimer = setTimeout(writeBackupNow, 600);
  }

  function downloadBackupJSON() {
    const blob = new Blob([JSON.stringify(buildBackupPayload(), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${DATA.source}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function restoreFromFile(file) {
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      if (Array.isArray(data.favorites)) state.favorites = new Set(data.favorites);
      if (data.ratings) state.ratings = data.ratings;
      if (data.pins) state.pins = data.pins;
      persist();
      refresh();
      alert("Respaldo restaurado desde JSON.");
    } catch (e) {
      alert("No se pudo leer ese archivo como respaldo valido.");
    }
  }

  // ---- DOM refs -----------------------------------------------------
  const grid = document.getElementById("grid");
  const emptyState = document.getElementById("empty-state");
  const videoName = document.getElementById("video-name");
  const searchTime = document.getElementById("search-time");
  const scoreRange = document.getElementById("score-range");
  const scoreValue = document.getElementById("score-value");
  const filterFavorites = document.getElementById("filter-favorites");
  const filterFaces = document.getElementById("filter-faces");
  const filterFlash = document.getElementById("filter-flash");
  const sortMode = document.getElementById("sort-mode");
  const viewMode = document.getElementById("view-mode");
  const stats = document.getElementById("stats");
  const exportBtn = document.getElementById("export-btn");

  const hoverPreview = document.getElementById("hover-preview");
  const hoverPreviewImg = document.getElementById("hover-preview-img");

  const lightbox = document.getElementById("lightbox");
  const lightboxImg = document.getElementById("lightbox-img");
  const lightboxMeta = document.getElementById("lightbox-meta");
  const burstStrip = document.getElementById("burst-strip");

  videoName.textContent = `${DATA.source} - ${formatTime(DATA.duration)}`;

  // ---- Helpers --------------------------------------------------------
  function formatTime(sec) {
    if (sec == null || isNaN(sec)) return "--:--";
    const m = Math.floor(sec / 60);
    const s = sec - m * 60;
    return `${String(m).padStart(2, "0")}:${s.toFixed(3).padStart(6, "0")}`;
  }

  function parseTimeQuery(q) {
    if (!q) return null;
    if (q.includes(":")) {
      const [m, s] = q.split(":");
      const mins = parseFloat(m) || 0;
      const secs = parseFloat(s) || 0;
      return mins * 60 + secs;
    }
    const v = parseFloat(q);
    return isNaN(v) ? null : v;
  }

  function exportPathFor(rec) {
    return state.pins[rec.id] || rec.full;
  }

  // ---- Filtering / sorting --------------------------------------------
  let filtered = [];
  let focusedIndex = -1;

  function computeFiltered() {
    let list = DATA.frames.slice();

    const t = parseTimeQuery(searchTime.value.trim());
    if (t !== null) list = list.filter((r) => Math.abs(r.time - t) <= 2);

    const minScore = parseFloat(scoreRange.value);
    list = list.filter((r) => r.score >= minScore);

    if (filterFavorites.checked) list = list.filter((r) => state.favorites.has(r.id));
    if (filterFaces.checked) list = list.filter((r) => r.face);
    if (filterFlash.checked) list = list.filter((r) => r.flash);

    if (sortMode.value === "score") list.sort((a, b) => b.score - a.score);
    else list.sort((a, b) => a.time - b.time);

    return list;
  }

  function refresh() {
    filtered = computeFiltered();
    focusedIndex = filtered.length ? Math.min(Math.max(focusedIndex, 0), filtered.length - 1) : -1;
    render();
    updateStats();
  }

  function updateStats() {
    stats.innerHTML = `
      ${DATA.frames.length} fotogramas totales<br/>
      ${filtered.length} visibles<br/>
      ${state.favorites.size} favoritos
    `;
  }

  // ---- Rendering --------------------------------------------------------
  function render() {
    grid.classList.toggle("storyboard", viewMode.value === "storyboard");
    grid.innerHTML = "";
    emptyState.classList.toggle("hidden", filtered.length > 0);

    const frag = document.createDocumentFragment();
    filtered.forEach((rec, i) => {
      frag.appendChild(buildCell(rec, i));
    });
    grid.appendChild(frag);
  }

  function buildCell(rec, index) {
    const cell = document.createElement("div");
    cell.className = "cell";
    cell.dataset.index = String(index);
    if (index === focusedIndex) cell.classList.add("focused");
    if (state.favorites.has(rec.id)) cell.classList.add("favorite");

    const img = document.createElement("img");
    img.src = rec.thumb;
    img.loading = "lazy";
    img.alt = `frame ${rec.id}`;
    cell.appendChild(img);

    const badgeRow = document.createElement("div");
    badgeRow.className = "badge-row";
    badgeRow.innerHTML = `
      <span class="badge">${formatTime(rec.time)}</span>
      <span class="badge">${rec.score.toFixed(1)}${rec.flash ? ' <span class="flash">&#9889;</span>' : ""}${rec.face ? ' <span class="face">&#9787;</span>' : ""}</span>
    `;
    cell.appendChild(badgeRow);

    if (state.ratings[rec.id]) {
      const rating = document.createElement("div");
      rating.className = "rating";
      rating.textContent = "*".repeat(state.ratings[rec.id]);
      cell.appendChild(rating);
    }

    if (state.favorites.has(rec.id)) {
      const dot = document.createElement("div");
      dot.className = "fav-dot";
      dot.textContent = "★";
      cell.appendChild(dot);
    }

    cell.addEventListener("click", () => {
      focusedIndex = index;
      render();
    });
    cell.addEventListener("dblclick", () => openLightbox(index));

    cell.addEventListener("mouseenter", () => {
      hoverPreviewImg.src = rec.full;
      hoverPreview.classList.remove("hidden");
    });
    cell.addEventListener("mousemove", (e) => {
      hoverPreview.style.left = Math.min(e.clientX + 20, window.innerWidth - 440) + "px";
      hoverPreview.style.top = Math.min(e.clientY + 20, window.innerHeight - 320) + "px";
    });
    cell.addEventListener("mouseleave", () => hoverPreview.classList.add("hidden"));

    return cell;
  }

  function scrollFocusedIntoView() {
    const el = grid.querySelector(`.cell[data-index="${focusedIndex}"]`);
    if (el) el.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
  }

  // ---- Favorites / ratings ----------------------------------------------
  function toggleFavorite(rec) {
    if (state.favorites.has(rec.id)) state.favorites.delete(rec.id);
    else state.favorites.add(rec.id);
    persist();
    render();
    updateStats();
  }

  function setRating(rec, value) {
    state.ratings[rec.id] = value;
    persist();
    render();
  }

  // ---- Lightbox / burst compare -------------------------------------------
  let lightboxIndex = -1;
  let burstIndex = 0;

  function openLightbox(index) {
    lightboxIndex = index;
    const rec = filtered[index];
    if (!rec) return;

    burstIndex = closestBurstIndex(rec);
    lightbox.classList.remove("hidden");
    renderLightbox();
  }

  function closeLightbox() {
    lightbox.classList.add("hidden");
    lightboxIndex = -1;
  }

  function closestBurstIndex(rec) {
    if (!rec.burst || !rec.burst.length) return -1;
    let best = 0;
    let bestDiff = Infinity;
    rec.burst.forEach((b, i) => {
      const diff = Math.abs(b.time - rec.time);
      if (diff < bestDiff) { bestDiff = diff; best = i; }
    });
    return best;
  }

  function currentLightboxImage(rec) {
    if (burstIndex >= 0 && rec.burst && rec.burst[burstIndex]) return rec.burst[burstIndex];
    return { path: rec.full, time: rec.time };
  }

  function renderLightbox() {
    const rec = filtered[lightboxIndex];
    if (!rec) return;
    const img = currentLightboxImage(rec);
    lightboxImg.src = img.path;

    const pinned = state.pins[rec.id];
    lightboxMeta.innerHTML = `
      ${formatTime(img.time)} &middot; score ${rec.score.toFixed(1)} &middot; cluster ${rec.cluster}
      ${rec.face ? " &middot; rostro" : ""}${rec.flash ? " &middot; flash" : ""}
      ${state.favorites.has(rec.id) ? " &middot; &#9733; favorito" : ""}
      ${state.ratings[rec.id] ? " &middot; " + "*".repeat(state.ratings[rec.id]) : ""}
      ${pinned ? ` &middot; exportara frame fijado (${pinned.split("/").pop()})` : ""}
    `;

    burstStrip.innerHTML = "";
    if (rec.burst && rec.burst.length) {
      rec.burst.forEach((b, i) => {
        const im = document.createElement("img");
        im.src = b.path;
        if (i === burstIndex) im.classList.add("active");
        if (pinned === b.path) im.classList.add("pinned");
        im.addEventListener("click", () => { burstIndex = i; renderLightbox(); });
        burstStrip.appendChild(im);
      });
    }
  }

  function moveBurst(delta) {
    const rec = filtered[lightboxIndex];
    if (!rec || !rec.burst || !rec.burst.length) return;
    burstIndex = Math.min(Math.max(burstIndex + delta, 0), rec.burst.length - 1);
    renderLightbox();
  }

  function pinCurrentBurstFrame() {
    const rec = filtered[lightboxIndex];
    if (!rec) return;
    const img = currentLightboxImage(rec);
    if (img.path === rec.full) {
      delete state.pins[rec.id];
    } else {
      state.pins[rec.id] = img.path;
    }
    persist();
    renderLightbox();
  }

  // ---- Export ------------------------------------------------------------
  function getFavoritesSorted() {
    return DATA.frames
      .filter((r) => state.favorites.has(r.id))
      .sort((a, b) => a.time - b.time);
  }

  async function exportSelected() {
    const recs = getFavoritesSorted();
    if (!recs.length) {
      alert("No hay favoritos seleccionados. Marca fotogramas con Espacio.");
      return;
    }
    const items = recs.map((r) => ({
      id: r.id,
      path: exportPathFor(r),
      name: `${String(r.id).padStart(5, "0")}.jpg`,
    }));

    const isFileProtocol = location.protocol === "file:";

    // Bajo file:// el navegador bloquea fetch() a recursos locales (falla en
    // silencio en varios navegadores), asi que ni lo intentamos: avisamos de
    // entrada y damos la alternativa que si funciona.
    if (isFileProtocol) {
      downloadBackupJSON();
      window.prompt(
        "Estas abriendo index.html directamente (file://). Por seguridad, el navegador " +
          "bloquea la exportacion automatica de imagenes en ese modo (aunque no muestre ningun error).\n\n" +
          "Para exportar: abre una terminal en esta carpeta y ejecuta:\n" +
          "  python3 -m http.server 8000\n" +
          "y luego abre http://localhost:8000 en el navegador.\n\n" +
          "Mientras tanto, ya descargamos tu respaldo JSON. Estas son las rutas de tus favoritos " +
          "(cópialas manualmente desde full/ si lo necesitas ahora):",
        items.map((i) => i.path).join("\n")
      );
      return;
    }

    if (window.showDirectoryPicker) {
      let dirHandle;
      try {
        dirHandle = await window.showDirectoryPicker();
      } catch (err) {
        if (err.name !== "AbortError") alert("No se pudo abrir el selector de carpeta: " + err.message);
        return;
      }
      try {
        for (const item of items) {
          const res = await fetch(item.path);
          if (!res.ok) throw new Error(`No se pudo leer ${item.path} (HTTP ${res.status})`);
          const blob = await res.blob();
          const fileHandle = await dirHandle.getFileHandle(item.name, { create: true });
          const writable = await fileHandle.createWritable();
          await writable.write(blob);
          await writable.close();
        }
        const manifestHandle = await dirHandle.getFileHandle("favoritos.json", { create: true });
        const manifestWritable = await manifestHandle.createWritable();
        await manifestWritable.write(JSON.stringify(buildBackupPayload(), null, 2));
        await manifestWritable.close();
        alert(`${items.length} fotogramas exportados junto a favoritos.json.`);
      } catch (err) {
        alert("La exportacion fallo a mitad de camino: " + err.message);
      }
      return;
    }

    // Navegadores sin File System Access API (Firefox, Safari): descarga
    // cada imagen como blob individual.
    let anyFailed = false;
    for (const item of items) {
      try {
        const res = await fetch(item.path);
        if (!res.ok) throw new Error("HTTP " + res.status);
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = item.name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        await new Promise((r) => setTimeout(r, 150));
      } catch (e) {
        anyFailed = true;
      }
    }
    downloadBackupJSON();
    if (anyFailed) {
      window.prompt(
        "Algunas descargas fallaron. Copia manualmente estas rutas relativas desde full/:",
        items.map((i) => i.path).join("\n")
      );
    } else {
      alert(`${items.length} fotogramas descargados junto al respaldo JSON.`);
    }
  }

  // ---- Events --------------------------------------------------------
  searchTime.addEventListener("input", refresh);
  scoreRange.addEventListener("input", () => {
    scoreValue.textContent = parseFloat(scoreRange.value).toFixed(1);
    refresh();
  });
  filterFavorites.addEventListener("change", refresh);
  filterFaces.addEventListener("change", refresh);
  filterFlash.addEventListener("change", refresh);
  sortMode.addEventListener("change", refresh);
  viewMode.addEventListener("change", refresh);
  exportBtn.addEventListener("click", exportSelected);

  const backupConnectBtn = document.getElementById("backup-connect-btn");
  const backupDownloadBtn = document.getElementById("backup-download-btn");
  const backupRestoreBtn = document.getElementById("backup-restore-btn");
  const backupRestoreInput = document.getElementById("backup-restore-input");
  backupConnectBtn.addEventListener("click", connectBackupFile);
  backupDownloadBtn.addEventListener("click", downloadBackupJSON);
  backupRestoreBtn.addEventListener("click", () => backupRestoreInput.click());
  backupRestoreInput.addEventListener("change", () => {
    const file = backupRestoreInput.files[0];
    if (file) restoreFromFile(file);
    backupRestoreInput.value = "";
  });

  lightbox.addEventListener("click", (e) => {
    if (e.target === lightbox) closeLightbox();
  });

  document.addEventListener("keydown", (e) => {
    const inLightbox = !lightbox.classList.contains("hidden");

    if (inLightbox) {
      if (e.key === "Escape") { closeLightbox(); return; }
      if (e.key === "j" || e.key === "J") { moveBurst(-1); return; }
      if (e.key === "l" || e.key === "L") { moveBurst(1); return; }
      if (e.key === "p" || e.key === "P") { pinCurrentBurstFrame(); return; }
      if (e.key === "ArrowLeft") { navigateFocused(-1); openLightbox(focusedIndex); return; }
      if (e.key === "ArrowRight") { navigateFocused(1); openLightbox(focusedIndex); return; }
      if (e.key === " ") { e.preventDefault(); toggleFavorite(filtered[lightboxIndex]); renderLightbox(); return; }
      if (/^[1-5]$/.test(e.key)) { setRating(filtered[lightboxIndex], parseInt(e.key, 10)); renderLightbox(); return; }
      return;
    }

    if (document.activeElement === searchTime) return;

    if (e.key === "ArrowLeft") { e.preventDefault(); navigateFocused(-1); return; }
    if (e.key === "ArrowRight") { e.preventDefault(); navigateFocused(1); return; }
    if (e.key === " ") {
      e.preventDefault();
      if (filtered[focusedIndex]) toggleFavorite(filtered[focusedIndex]);
      return;
    }
    if (e.key === "Enter") {
      if (focusedIndex >= 0) openLightbox(focusedIndex);
      return;
    }
    if (/^[1-5]$/.test(e.key)) {
      if (filtered[focusedIndex]) setRating(filtered[focusedIndex], parseInt(e.key, 10));
      return;
    }
    if (e.key === "e" || e.key === "E") { exportSelected(); return; }
  });

  function navigateFocused(delta) {
    if (!filtered.length) return;
    focusedIndex = Math.min(Math.max(focusedIndex + delta, 0), filtered.length - 1);
    render();
    scrollFocusedIntoView();
  }

  // ---- Init --------------------------------------------------------
  refresh();
  if (filtered.length) focusedIndex = 0;
  render();
  initBackupHandle();
})();
