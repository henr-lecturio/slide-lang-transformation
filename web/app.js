const el = {
  status: document.getElementById("run-status"),
  configMeta: document.getElementById("config-meta"),
  saveRoi: document.getElementById("save-roi"),
  roiX0: document.getElementById("roi_x0"),
  roiY0: document.getElementById("roi_y0"),
  roiX1: document.getElementById("roi_x1"),
  roiY1: document.getElementById("roi_y1"),
  keyframeSettleFrames: document.getElementById("keyframe_settle_frames"),
  overlayTime: document.getElementById("overlay-time"),
  regenOverlay: document.getElementById("regen-overlay"),
  refreshOverlay: document.getElementById("refresh-overlay"),
  overlayImage: document.getElementById("overlay-image"),
  overlayLog: document.getElementById("overlay-log"),
  startRun: document.getElementById("start-run"),
  refreshRuns: document.getElementById("refresh-runs"),
  runLog: document.getElementById("run-log"),
  runSelect: document.getElementById("run-select"),
  imageType: document.getElementById("image-type"),
  loadImages: document.getElementById("load-images"),
  runSummary: document.getElementById("run-summary"),
  csvPreview: document.getElementById("csv-preview"),
  thumbs: document.getElementById("thumbs"),
};

const state = {
  selectedRunId: null,
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
  el.runLog.textContent = logs.join("\n");
}

function setConfig(cfg) {
  el.roiX0.value = cfg.ROI_X0;
  el.roiY0.value = cfg.ROI_Y0;
  el.roiX1.value = cfg.ROI_X1;
  el.roiY1.value = cfg.ROI_Y1;
  el.keyframeSettleFrames.value = cfg.KEYFRAME_SETTLE_FRAMES;
  el.configMeta.textContent = `VIDEO_PATH: ${cfg.VIDEO_PATH} | settle: ${cfg.KEYFRAME_SETTLE_FRAMES}`;
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

async function loadRuns() {
  const data = await apiGet("/api/runs");
  setStatus(data.current || {});

  const runs = data.runs || [];
  const prev = state.selectedRunId;

  el.runSelect.innerHTML = "";
  for (const run of runs) {
    const opt = document.createElement("option");
    opt.value = run.id;
    opt.textContent = `${run.id} | events ${run.event_count} | slide ${run.slide_images}`;
    el.runSelect.appendChild(opt);
  }

  if (runs.length === 0) {
    state.selectedRunId = null;
    el.runSummary.textContent = "No runs yet";
    el.csvPreview.textContent = "";
    el.thumbs.innerHTML = "";
    return;
  }

  const fallback = runs[0].id;
  state.selectedRunId = runs.some((r) => r.id === prev) ? prev : fallback;
  el.runSelect.value = state.selectedRunId;

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

async function loadImages() {
  const runId = el.runSelect.value;
  if (!runId) return;
  const type = el.imageType.value;
  const data = await apiGet(`/api/runs/${encodeURIComponent(runId)}/images?type=${encodeURIComponent(type)}`);
  const images = data.images || [];

  el.thumbs.innerHTML = "";
  const maxItems = 120;
  const shown = images.slice(0, maxItems);

  for (const item of shown) {
    const card = document.createElement("div");
    card.className = "thumb";

    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = `${item.url}?v=${Date.now()}`;
    img.alt = item.name;

    const name = document.createElement("div");
    name.className = "name";
    name.textContent = item.name;

    card.appendChild(img);
    card.appendChild(name);
    el.thumbs.appendChild(card);
  }
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
  el.saveRoi.addEventListener("click", () => runTask(saveConfig));
  el.regenOverlay.addEventListener("click", () => runTask(regenerateOverlay));
  el.refreshOverlay.addEventListener("click", () => runTask(loadOverlay));
  el.startRun.addEventListener("click", () => runTask(startRun));
  el.refreshRuns.addEventListener("click", () => runTaskImmediate(loadRuns));
  el.runSelect.addEventListener("change", () => runTask(loadRunDetails));
  el.loadImages.addEventListener("click", () => runTask(loadImages));
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
  await runTask(loadConfig);
  await runTask(loadOverlay);
  await runTask(loadRuns);
  setInterval(pollCurrent, 2000);
}

init();
