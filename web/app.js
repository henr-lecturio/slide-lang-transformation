const el = {
  status: document.getElementById("run-status"),
  tabButtons: document.querySelectorAll(".tab-btn"),
  panelHome: document.getElementById("panel-home"),
  panelAllRuns: document.getElementById("panel-all-runs"),
  panelRoi: document.getElementById("panel-roi"),
  configMeta: document.getElementById("config-meta"),
  saveRoi: document.getElementById("save-roi"),
  roiX0: document.getElementById("roi_x0"),
  roiY0: document.getElementById("roi_y0"),
  roiX1: document.getElementById("roi_x1"),
  roiY1: document.getElementById("roi_y1"),
  keyframeSettleFrames: document.getElementById("keyframe_settle_frames"),
  keyframeStableEndGuardFrames: document.getElementById("keyframe_stable_end_guard_frames"),
  keyframeStableLookaheadFrames: document.getElementById("keyframe_stable_lookahead_frames"),
  overlayTime: document.getElementById("overlay-time"),
  regenOverlay: document.getElementById("regen-overlay"),
  refreshOverlay: document.getElementById("refresh-overlay"),
  overlayImage: document.getElementById("overlay-image"),
  overlayLog: document.getElementById("overlay-log"),
  startRun: document.getElementById("start-run"),
  refreshRuns: document.getElementById("refresh-runs"),
  runLog: document.getElementById("run-log"),
  latestSummary: document.getElementById("latest-summary"),
  latestCsvPreview: document.getElementById("latest-csv-preview"),
  latestThumbs: document.getElementById("latest-thumbs"),
  latestImageType: document.getElementById("latest-image-type"),
  loadLatestImages: document.getElementById("load-latest-images"),
  runSelect: document.getElementById("run-select"),
  imageType: document.getElementById("image-type"),
  loadImages: document.getElementById("load-images"),
  runSummary: document.getElementById("run-summary"),
  csvPreview: document.getElementById("csv-preview"),
  thumbs: document.getElementById("thumbs"),
  imageModal: document.getElementById("image-modal"),
  imageModalBackdrop: document.getElementById("image-modal-backdrop"),
  imageModalClose: document.getElementById("image-modal-close"),
  imageModalImg: document.getElementById("image-modal-img"),
  imageModalCaption: document.getElementById("image-modal-caption"),
};

const state = {
  selectedRunId: null,
  latestRunId: null,
};

async function apiGet(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const body = await safeJson(res);
    throw new Error(body.error || `GET ${url} failed (${res.status})`);
  }
  return await res.json();
}

async function apiPost(url, payload = {}) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await safeJson(res);
  if (!res.ok) {
    throw new Error(body.error || `POST ${url} failed (${res.status})`);
  }
  return body;
}

async function safeJson(res) {
  try {
    return await res.json();
  } catch {
    return {};
  }
}

function setStatus(current) {
  const status = current.status || "idle";
  const runId = current.run_id ? `, run ${current.run_id}` : "";
  el.status.textContent = `status: ${status}${runId}`;
  el.startRun.disabled = status === "running";

  const logs = (current.log_tail || []).slice(-120);
  const nextLog = logs.join("\n");
  if (el.runLog.textContent !== nextLog) {
    el.runLog.textContent = nextLog;
    // Always keep newest lines visible while the run is progressing.
    el.runLog.scrollTop = el.runLog.scrollHeight;
  }
}

function setConfig(cfg) {
  el.roiX0.value = cfg.ROI_X0;
  el.roiY0.value = cfg.ROI_Y0;
  el.roiX1.value = cfg.ROI_X1;
  el.roiY1.value = cfg.ROI_Y1;
  el.keyframeSettleFrames.value = cfg.KEYFRAME_SETTLE_FRAMES;
  el.keyframeStableEndGuardFrames.value = cfg.KEYFRAME_STABLE_END_GUARD_FRAMES;
  el.keyframeStableLookaheadFrames.value = cfg.KEYFRAME_STABLE_LOOKAHEAD_FRAMES;
  el.configMeta.textContent = `VIDEO_PATH: ${cfg.VIDEO_PATH} | settle: ${cfg.KEYFRAME_SETTLE_FRAMES} | end_guard: ${cfg.KEYFRAME_STABLE_END_GUARD_FRAMES} | lookahead: ${cfg.KEYFRAME_STABLE_LOOKAHEAD_FRAMES}`;
}

function setActiveTab(tabName) {
  for (const btn of el.tabButtons) {
    const active = btn.dataset.tab === tabName;
    btn.classList.toggle("active", active);
  }
  el.panelHome.classList.toggle("active", tabName === "home");
  el.panelAllRuns.classList.toggle("active", tabName === "all-runs");
  el.panelRoi.classList.toggle("active", tabName === "roi");
}

async function loadConfig() {
  const cfg = await apiGet("/api/config");
  setConfig(cfg);
}

async function saveConfig() {
  const payload = {
    ROI_X0: Number(el.roiX0.value),
    ROI_Y0: Number(el.roiY0.value),
    ROI_X1: Number(el.roiX1.value),
    ROI_Y1: Number(el.roiY1.value),
    KEYFRAME_SETTLE_FRAMES: Number(el.keyframeSettleFrames.value),
    KEYFRAME_STABLE_END_GUARD_FRAMES: Number(el.keyframeStableEndGuardFrames.value),
    KEYFRAME_STABLE_LOOKAHEAD_FRAMES: Number(el.keyframeStableLookaheadFrames.value),
  };
  await apiPost("/api/config", payload);
  await loadConfig();
}

async function loadOverlay() {
  const data = await apiGet("/api/overlay");
  if (!data.exists) {
    el.overlayImage.removeAttribute("src");
    return;
  }
  const v = data.mtime || Date.now();
  el.overlayImage.src = `${data.url}?v=${v}`;
}

async function regenerateOverlay() {
  const t = Number(el.overlayTime.value || 30);
  const result = await apiPost("/api/overlay", { time_sec: t });
  el.overlayLog.textContent = (result.output || "").trim();
  await loadOverlay();
}

function clearLatestOutput() {
  el.latestSummary.textContent = "No runs yet";
  el.latestCsvPreview.textContent = "";
  el.latestThumbs.innerHTML = "";
}

function clearSelectedRunOutput() {
  el.runSummary.textContent = "No runs yet";
  el.csvPreview.textContent = "";
  el.thumbs.innerHTML = "";
}

function renderRunSelect(runs) {
  el.runSelect.innerHTML = "";
  for (const run of runs) {
    const opt = document.createElement("option");
    opt.value = run.id;
    opt.textContent = `${run.id} | events ${run.event_count} | slide ${run.slide_images}`;
    el.runSelect.appendChild(opt);
  }
}

async function loadRuns() {
  const data = await apiGet("/api/runs");
  setStatus(data.current || {});

  const runs = data.runs || [];
  state.latestRunId = runs.length > 0 ? runs[0].id : null;
  const prev = state.selectedRunId;

  renderRunSelect(runs);

  if (runs.length === 0) {
    state.selectedRunId = null;
    clearLatestOutput();
    clearSelectedRunOutput();
    return;
  }

  const fallback = runs[0].id;
  state.selectedRunId = runs.some((r) => r.id === prev) ? prev : fallback;
  el.runSelect.value = state.selectedRunId;

  await loadLatestRunDetails();
  await loadLatestImages();
  await loadRunDetails();
}

async function loadRunDetails() {
  const runId = el.runSelect.value;
  if (!runId) return;
  state.selectedRunId = runId;

  const detail = await apiGet(`/api/runs/${encodeURIComponent(runId)}`);
  el.runSummary.textContent = `run=${detail.id} | events=${detail.event_count} | slide=${detail.slide_images} | full=${detail.full_images}`;
  el.csvPreview.textContent = (detail.csv_preview || []).join("\n");
}

async function loadLatestRunDetails() {
  const runId = state.latestRunId;
  if (!runId) {
    clearLatestOutput();
    return;
  }

  const detail = await apiGet(`/api/runs/${encodeURIComponent(runId)}`);
  el.latestSummary.textContent = `latest=${detail.id} | events=${detail.event_count} | slide=${detail.slide_images} | full=${detail.full_images}`;
  el.latestCsvPreview.textContent = (detail.csv_preview || []).join("\n");
}

async function renderImages(runId, type, target) {
  if (!runId) {
    target.innerHTML = "";
    return;
  }
  const data = await apiGet(`/api/runs/${encodeURIComponent(runId)}/images?type=${encodeURIComponent(type)}`);
  const images = data.images || [];

  target.innerHTML = "";
  const maxItems = 120;
  const shown = images.slice(0, maxItems);

  for (const item of shown) {
    const card = document.createElement("div");
    card.className = "thumb";

    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = `${item.url}?v=${Date.now()}`;
    img.alt = item.name;
    img.addEventListener("click", () => openImageModal(item.url, item.name));

    const name = document.createElement("div");
    name.className = "name";
    name.textContent = item.name;

    card.appendChild(img);
    card.appendChild(name);
    target.appendChild(card);
  }
}

function openImageModal(url, name) {
  const sep = url.includes("?") ? "&" : "?";
  el.imageModalImg.src = `${url}${sep}v=${Date.now()}`;
  el.imageModalCaption.textContent = name || "";
  el.imageModal.classList.add("open");
  el.imageModal.setAttribute("aria-hidden", "false");
}

function closeImageModal() {
  el.imageModal.classList.remove("open");
  el.imageModal.setAttribute("aria-hidden", "true");
  el.imageModalImg.removeAttribute("src");
  el.imageModalCaption.textContent = "";
}

async function loadImages() {
  const runId = el.runSelect.value;
  if (!runId) return;
  const type = el.imageType.value;
  await renderImages(runId, type, el.thumbs);
}

async function loadLatestImages() {
  const runId = state.latestRunId;
  if (!runId) {
    el.latestThumbs.innerHTML = "";
    return;
  }
  const type = el.latestImageType.value;
  await renderImages(runId, type, el.latestThumbs);
}

async function startRun() {
  await apiPost("/api/runs", {});
  await loadRuns();
}

async function pollCurrent() {
  try {
    const current = await apiGet("/api/runs/current");
    setStatus(current);
    if (current.status === "done" || current.status === "error") {
      await loadRuns();
    }
  } catch (err) {
    console.error(err);
  }
}

function bindEvents() {
  for (const btn of el.tabButtons) {
    btn.addEventListener("click", () => setActiveTab(btn.dataset.tab));
  }
  el.saveRoi.addEventListener("click", () => runTask(saveConfig));
  el.regenOverlay.addEventListener("click", () => runTask(regenerateOverlay));
  el.refreshOverlay.addEventListener("click", () => runTask(loadOverlay));
  el.startRun.addEventListener("click", () => runTask(startRun));
  el.refreshRuns.addEventListener("click", () => runTaskImmediate(loadRuns));
  el.loadLatestImages.addEventListener("click", () => runTask(loadLatestImages));
  el.runSelect.addEventListener("change", () => runTask(loadRunDetails));
  el.loadImages.addEventListener("click", () => runTask(loadImages));
  el.imageModalClose.addEventListener("click", closeImageModal);
  el.imageModalBackdrop.addEventListener("click", closeImageModal);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && el.imageModal.classList.contains("open")) {
      closeImageModal();
    }
  });
}

let busy = false;
async function runTask(fn) {
  if (busy) return;
  busy = true;
  try {
    await fn();
  } catch (err) {
    alert(err.message || String(err));
  } finally {
    busy = false;
  }
}

async function runTaskImmediate(fn) {
  try {
    await fn();
  } catch (err) {
    alert(err.message || String(err));
  }
}

async function init() {
  bindEvents();
  setActiveTab("home");
  await runTask(loadConfig);
  await runTask(loadOverlay);
  await runTask(loadRuns);
  setInterval(pollCurrent, 2000);
}

init();
