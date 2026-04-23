const form = document.querySelector("#generate-form");
const previewButton = document.getElementById("preview-button");

function bindRangeOutputs() {
  document.querySelectorAll("input[type='range'][data-output]").forEach((input) => {
    const output = document.getElementById(input.dataset.output);
    if (!output) return;
    const render = () => {
      output.textContent = input.name === "segment_length" ? `${input.value} chars` : input.value;
    };
    input.addEventListener("input", render);
    render();
  });
}

function appendLog(message) {
  const box = document.getElementById("log-box");
  if (!box) return;
  const line = document.createElement("div");
  line.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

function setStatus(status, message, progress = 0) {
  const badge = document.getElementById("job-status-badge");
  const bar = document.getElementById("progress-bar");
  const text = document.getElementById("progress-text");
  if (badge) {
    badge.className = `badge ${status || "idle"}`;
    badge.textContent = status || "idle";
  }
  if (bar) {
    bar.style.width = `${progress || 0}%`;
  }
  if (text) {
    text.textContent = message || "";
  }
}

function pushToast(message, type = "info") {
  const stack = document.getElementById("toast-stack");
  if (!stack) return;
  const item = document.createElement("div");
  item.className = `toast ${type}`;
  item.textContent = message;
  stack.appendChild(item);
  window.setTimeout(() => item.remove(), 4200);
}

function renderWarnings(messages) {
  const box = document.getElementById("warnings-box");
  if (!box) return;
  if (!messages.length) {
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }
  box.classList.remove("hidden");
  box.innerHTML = messages.map((msg) => `<p>${msg}</p>`).join("");
}

function renderResult(result) {
  const box = document.getElementById("result-box");
  if (!box || !result) return;
  const { output_files: files, duration_seconds: duration, title } = result;
  box.classList.remove("hidden");
  box.innerHTML = `
    <p><strong>${title}</strong></p>
    <p>Duracion final: ${duration ?? "N/A"} s</p>
    <audio controls preload="metadata" src="/audio/${files.wav}"></audio>
    <div class="history-actions">
      <a href="/download/${files.wav}">Descargar WAV</a>
      ${files.mp3 ? `<a href="/download/${files.mp3}">Descargar MP3</a>` : ""}
      ${files.m4a ? `<a href="/download/${files.m4a}">Descargar M4A</a>` : ""}
    </div>
  `;
}

function clearPreview() {
  const panel = document.getElementById("preview-panel");
  const box = document.getElementById("preview-box");
  const meta = document.getElementById("preview-meta");
  if (panel) panel.classList.add("hidden");
  if (box) box.textContent = "";
  if (meta) meta.textContent = "";
}

function renderPreview(payload) {
  const panel = document.getElementById("preview-panel");
  const box = document.getElementById("preview-box");
  const meta = document.getElementById("preview-meta");
  if (!panel || !box || !meta) return;
  box.textContent = payload.preview_text || "No hay texto util para sintetizar.";
  meta.textContent = `${payload.variant || ""}${payload.title ? ` | ${payload.title}` : ""}`;
  panel.classList.remove("hidden");
}

async function refreshHistory() {
  const grid = document.getElementById("history-grid");
  if (!grid) return;
  const response = await fetch("/history?format=json");
  if (!response.ok) return;
  const items = await response.json();
  if (!items.length) {
    grid.innerHTML = `<div class="empty-state"><p>No hay renders todavia. El primer audio aparecera aqui.</p></div>`;
    return;
  }
  grid.innerHTML = items.slice(0, 8).map((item) => `
    <article class="history-card">
      <div class="history-meta">
        <span>${item.variant}</span>
        <span>${new Date(item.created_at).toLocaleString()}</span>
      </div>
      <h4>${item.title}</h4>
      <p class="muted">Voz: ${item.voice_name ?? "sin referencia"}</p>
      <audio controls preload="none" src="/audio/${item.output_files.wav}"></audio>
      <div class="history-actions">
        <div class="history-tags">
          ${(item.playlist_names || []).map((name) => `<span class="playlist-pill">${name}</span>`).join("")}
        </div>
        <a href="/download/${item.output_files.wav}">Descargar WAV</a>
        ${item.output_files.mp3 ? `<a href="/download/${item.output_files.mp3}">MP3</a>` : ""}
        ${item.output_files.m4a ? `<a href="/download/${item.output_files.m4a}">M4A</a>` : ""}
      </div>
    </article>
  `).join("");
}

function openEventStream(jobId) {
  const source = new EventSource(`/events/${jobId}`);
  const warnings = [];

  source.addEventListener("snapshot", (event) => {
    const data = JSON.parse(event.data || "{}");
    setStatus(data.status || "pending", data.message || "Preparando", data.progress || 0);
    renderWarnings(data.warnings || []);
    (data.logs || []).forEach((message) => appendLog(message));
    if (data.result) {
      renderResult(data.result);
    }
  });

  source.addEventListener("progress", (event) => {
    const data = JSON.parse(event.data);
    setStatus(data.status, data.message, data.progress || 0);
  });

  source.addEventListener("log", (event) => {
    const data = JSON.parse(event.data);
    appendLog(data.message);
  });

  source.addEventListener("warning", (event) => {
    const data = JSON.parse(event.data);
    warnings.push(data.message);
    renderWarnings(warnings);
    pushToast(data.message, "info");
  });

  source.addEventListener("completed", async (event) => {
    const data = JSON.parse(event.data);
    setStatus("completed", "Audio generado correctamente.", 100);
    renderResult(data.result);
    pushToast("Render finalizado.", "success");
    await refreshHistory();
    source.close();
    const submit = form?.querySelector("button[type='submit']");
    if (submit) submit.disabled = false;
    if (previewButton) previewButton.disabled = false;
  });

  source.addEventListener("failed", (event) => {
    const data = JSON.parse(event.data);
    setStatus("failed", data.error, 100);
    appendLog(data.error);
    pushToast(data.error, "error");
    source.close();
    const submit = form?.querySelector("button[type='submit']");
    if (submit) submit.disabled = false;
    if (previewButton) previewButton.disabled = false;
  });

  source.onerror = () => {
    const submit = form?.querySelector("button[type='submit']");
    setStatus("failed", "Se perdio la conexion con el proceso de render.", 100);
    appendLog("Stream SSE interrumpido o servidor reiniciado.");
    pushToast("La conexion de progreso se interrumpio.", "error");
    source.close();
    if (submit) submit.disabled = false;
    if (previewButton) previewButton.disabled = false;
  };
}

async function handleSubmit(event) {
  event.preventDefault();
  const submit = form.querySelector("button[type='submit']");
  submit.disabled = true;
  if (previewButton) previewButton.disabled = true;
  document.getElementById("log-box").innerHTML = "";
  document.getElementById("result-box").classList.add("hidden");
  renderWarnings([]);
  setStatus("running", "Enviando solicitud...", 2);

  const payload = new FormData(form);
  if (!payload.has("normalize_audio")) {
    payload.append("normalize_audio", "false");
  }
  if (!payload.has("export_mp3")) {
    payload.append("export_mp3", "false");
  }
  if (!payload.has("export_m4a")) {
    payload.append("export_m4a", "false");
  }

  try {
    const response = await fetch("/generate", {
      method: "POST",
      body: payload,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "No se pudo iniciar la generacion.");
    }
    appendLog(`Job ${data.job_id} creado.`);
    openEventStream(data.job_id);
  } catch (error) {
    setStatus("failed", error.message, 100);
    pushToast(error.message, "error");
    submit.disabled = false;
    if (previewButton) previewButton.disabled = false;
  }
}

async function handlePreview() {
  if (!form || !previewButton) return;
  previewButton.disabled = true;
  const originalLabel = previewButton.textContent;
  previewButton.textContent = "Analizando...";

  const payload = new FormData(form);
  if (!payload.has("normalize_audio")) {
    payload.append("normalize_audio", "false");
  }

  try {
    const response = await fetch("/preview-text", {
      method: "POST",
      body: payload,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "No se pudo preparar la previsualizacion.");
    }
    renderPreview(data);
    pushToast("Previsualizacion actualizada.", "info");
  } catch (error) {
    clearPreview();
    pushToast(error.message, "error");
  } finally {
    previewButton.disabled = false;
    previewButton.textContent = originalLabel;
  }
}

function initHistoryPlayer() {
  const playerShell = document.getElementById("history-player-shell");
  const player = document.getElementById("history-audio-player");
  const title = document.getElementById("history-player-title");
  const modeLabel = document.getElementById("history-player-mode");
  const meta = document.getElementById("history-player-meta");
  const description = document.getElementById("history-player-description");
  const currentTime = document.getElementById("history-current-time");
  const duration = document.getElementById("history-duration");
  const seek = document.getElementById("history-seek");
  const togglePlay = document.getElementById("history-toggle-play");
  const backward = document.getElementById("history-backward");
  const forward = document.getElementById("history-forward");
  const speed = document.getElementById("history-speed");
  const downloadWav = document.getElementById("history-download-wav");
  const downloadMp3 = document.getElementById("history-download-mp3");
  const downloadM4a = document.getElementById("history-download-m4a");
  const triggers = document.querySelectorAll("[data-audio-src]");
  if (!playerShell || !player || !title || !triggers.length) return;

  let activeButton = null;
  let currentMode = "full";
  let previewTimeout = null;

  const clearPreviewTimeout = () => {
    if (previewTimeout) {
      window.clearTimeout(previewTimeout);
      previewTimeout = null;
    }
  };

  const formatTime = (value) => {
    if (!Number.isFinite(value) || value < 0) return "0:00";
    const minutes = Math.floor(value / 60);
    const seconds = Math.floor(value % 60).toString().padStart(2, "0");
    return `${minutes}:${seconds}`;
  };

  const setActive = (button) => {
    activeButton = button;
    triggers.forEach((button) => {
      button.classList.toggle("is-playing", button === activeButton);
    });
  };

  const updateDownloads = (button) => {
    const files = [
      [downloadWav, button?.dataset.audioWav],
      [downloadMp3, button?.dataset.audioMp3],
      [downloadM4a, button?.dataset.audioM4a],
    ];
    files.forEach(([link, href]) => {
      if (!link) return;
      if (href) {
        link.href = href;
        link.classList.remove("hidden");
      } else {
        link.classList.add("hidden");
        link.removeAttribute("href");
      }
    });
  };

  const syncProgress = () => {
    if (currentTime) currentTime.textContent = formatTime(player.currentTime);
    if (duration) duration.textContent = formatTime(player.duration);
    if (seek) {
      const max = Number.isFinite(player.duration) && player.duration > 0 ? player.duration : 100;
      seek.max = String(max);
      seek.value = String(Math.min(player.currentTime || 0, max));
    }
  };

  const syncPanel = (button, mode) => {
    if (!button) return;
    playerShell.classList.remove("hidden");
    currentMode = mode;
    title.textContent = button.dataset.audioTitle || "Episodio";
    if (modeLabel) modeLabel.textContent = mode === "preview" ? "Mini Preview" : "Now Playing";
    if (meta) meta.textContent = button.dataset.audioMeta || "";
    if (description) description.textContent = button.dataset.audioDescription || "";
    updateDownloads(button);
    if (togglePlay) togglePlay.textContent = player.paused ? "Play" : "Pause";
  };

  const playTrack = async (button, mode) => {
    const src = button.dataset.audioSrc;
    if (!src) return;

    clearPreviewTimeout();
    syncPanel(button, mode);

    const resolvedSrc = new URL(src, window.location.origin).href;
    const isSameTrack = player.currentSrc === resolvedSrc;
    if (!isSameTrack) {
      player.src = src;
      player.currentTime = 0;
    } else if (mode === "preview") {
      player.currentTime = 0;
    }

    try {
      await player.play();
      setActive(button);
      if (togglePlay) togglePlay.textContent = "Pause";
      if (mode === "preview") {
        previewTimeout = window.setTimeout(() => {
          player.pause();
          if (modeLabel) modeLabel.textContent = "Mini Preview";
        }, 20000);
      }
    } catch (error) {
      console.error("No se pudo reproducir el audio.", error);
    }
  };

  triggers.forEach((button) => {
    button.addEventListener("click", async () => {
      const mode = button.dataset.playMode || "full";
      const src = button.dataset.audioSrc;
      if (!src) return;
      const resolvedSrc = new URL(src, window.location.origin).href;
      const isSameTrack = player.currentSrc === resolvedSrc;
      const isSameControl = activeButton === button;

      if (isSameTrack && isSameControl && !player.paused) {
        clearPreviewTimeout();
        player.pause();
        setActive(null);
        if (togglePlay) togglePlay.textContent = "Play";
        return;
      }
      await playTrack(button, mode);
    });
  });

  togglePlay?.addEventListener("click", async () => {
    if (!player.currentSrc) return;
    if (player.paused) {
      clearPreviewTimeout();
      try {
        await player.play();
        if (togglePlay) togglePlay.textContent = "Pause";
      } catch (error) {
        console.error("No se pudo reanudar el audio.", error);
      }
      return;
    }
    player.pause();
  });

  backward?.addEventListener("click", () => {
    player.currentTime = Math.max(0, player.currentTime - 10);
    syncProgress();
  });

  forward?.addEventListener("click", () => {
    const max = Number.isFinite(player.duration) ? player.duration : player.currentTime + 10;
    player.currentTime = Math.min(max, player.currentTime + 10);
    syncProgress();
  });

  speed?.addEventListener("change", () => {
    player.playbackRate = Number(speed.value || 1);
  });

  seek?.addEventListener("input", () => {
    player.currentTime = Number(seek.value || 0);
    syncProgress();
  });

  player.addEventListener("loadedmetadata", syncProgress);
  player.addEventListener("timeupdate", syncProgress);

  player.addEventListener("pause", () => {
    clearPreviewTimeout();
    if (!player.ended) {
      setActive(null);
    }
    if (togglePlay) togglePlay.textContent = "Play";
  });

  player.addEventListener("ended", () => {
    clearPreviewTimeout();
    setActive(null);
    if (togglePlay) togglePlay.textContent = "Play";
    syncProgress();
  });
}

bindRangeOutputs();
initHistoryPlayer();
if (form) {
  form.addEventListener("submit", handleSubmit);
  form.addEventListener("input", clearPreview);
  form.addEventListener("change", clearPreview);
}

if (previewButton) {
  previewButton.addEventListener("click", handlePreview);
}
