import { el } from "./dom.js";
import { state } from "./state.js";
import { apiGet, apiPost } from "./api.js";
import { formatRunIdLabel, formatUsd } from "./ui-core.js";
import { openImageModal } from "./modals.js";

let runTaskImmediateHandler = async (fn) => { await fn(); };
let setStatusHandler = () => {};

export function configureRunsModule({ runTaskImmediate, setStatus } = {}) {
  if (runTaskImmediate) runTaskImmediateHandler = runTaskImmediate;
  if (setStatus) setStatusHandler = setStatus;
}

function preferredLatestRunId(runs, current) {
  const currentRunId = current?.run_id || "";
  const currentStatus = current?.status || "";
  if (currentRunId && currentStatus && currentStatus !== "idle") {
    return currentRunId;
  }
  return runs.length > 0 ? runs[0].id : null;
}

function getDownloadLinks(detail, { includeVideo = true, includeNonVideo = true } = {}) {
  if (!detail) return [];
  return [
    ...(includeNonVideo ? [
      { label: "Translated Text JSON", url: detail.translated_text_json_url, name: "slide_text_map_final_translated.json" },
      { label: "Translated Text CSV", url: detail.translated_text_csv_url, name: "slide_text_map_final_translated.csv" },
      { label: "TTS Manifest", url: detail.tts_manifest_url, name: "tts_manifest.json" },
      { label: "TTS Full Audio", url: detail.tts_full_audio_url, name: "full_transcript.wav" },
      { label: "TTS Alignment JSON", url: detail.tts_alignment_json_url, name: "segment_alignment.json" },
      { label: "TTS Alignment CSV", url: detail.tts_alignment_csv_url, name: "segment_alignment.csv" },
      { label: "Timeline JSON", url: detail.video_timeline_json_url, name: "timeline.json" },
      { label: "Timeline CSV", url: detail.video_timeline_csv_url, name: "timeline.csv" },
    ] : []),
    ...(includeVideo ? [
      { label: "Subtitles", url: detail.exported_srt_url, name: detail.exported_video_name ? detail.exported_video_name.replace(/\.mp4$/i, ".srt") : "final.srt" },
      { label: "MP4", url: detail.exported_video_url, name: detail.exported_video_name || "final.mp4" },
    ] : []),
  ].filter((item) => item.url);
}

function renderDownloadLinks(target, detail, options = {}) {
  if (!target) return;
  target.innerHTML = "";
  if (!detail) return;

  const links = getDownloadLinks(detail, options);

  if (links.length === 0) {
    const empty = document.createElement("span");
    empty.className = "muted";
    empty.textContent = "No export files available.";
    target.appendChild(empty);
    return;
  }

  for (const link of links) {
    const a = document.createElement("a");
    a.className = "summary-link";
    a.href = link.url;
    a.download = link.name || "";
    a.textContent = link.label;
    target.appendChild(a);
  }
}

function renderLatestInfo(detail) {
  if (!el.latestInfoGrid) return;
  el.latestInfoGrid.innerHTML = "";
  if (!detail) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "No run details available.";
    el.latestInfoGrid.appendChild(empty);
    return;
  }

  const facts = [
    ["Run", formatRunIdLabel(detail.id)],
    ["Run Status", detail.run_status || "-"],
    ["Available", detail.highest_available_label || "no output yet"],
    ["Upscale Mode", detail.upscale_mode_used || "-"],
    ["Upscale Cost", formatUsd(detail.upscale_estimated_cost_usd)],
    ["Base Events", String(detail.event_count ?? 0)],
    ["Final Events", String(detail.final_event_count ?? 0)],
    ["Final Slide Images", String(detail.final_slide_images ?? 0)],
    ["Translated Slide Images", String(detail.translated_slide_images ?? 0)],
    ["Upscaled Slide Images", String(detail.upscaled_slide_images ?? 0)],
    ["Translated x4 Slides", String(detail.translated_upscaled_slide_images ?? 0)],
    ["Translated Text Events", String(detail.translated_text_events ?? 0)],
    ["TTS Segments", String(detail.tts_segments ?? 0)],
  ];

  for (const [labelText, valueText] of facts) {
    const item = document.createElement("div");
    item.className = "output-info-item";
    const label = document.createElement("div");
    label.className = "output-info-label";
    label.textContent = labelText;
    const value = document.createElement("div");
    value.className = "output-info-value";
    value.textContent = valueText;
    item.appendChild(label);
    item.appendChild(value);
    el.latestInfoGrid.appendChild(item);
  }
}

export async function loadOverlay() {
  const data = await apiGet("/api/overlay");
  if (!data.exists) {
    el.overlayImage.removeAttribute("src");
    return;
  }
  const v = data.mtime || Date.now();
  el.overlayImage.src = `${data.url}?v=${v}`;
}

export async function regenerateOverlay() {
  const t = Number(el.overlayTime.value || 30);
  const result = await apiPost("/api/overlay", { time_sec: t });
  if (el.roiLog) {
    el.roiLog.textContent = (result.output || "").trim();
    el.roiLog.scrollTop = el.roiLog.scrollHeight;
  }
  await loadOverlay();
}

function clearLatestOutput() {
  renderLatestInfo(null);
  renderDownloadLinks(el.latestDownloads, null, { includeVideo: false, includeNonVideo: true });
  renderDownloadLinks(el.latestExports, null, { includeVideo: true, includeNonVideo: false });
  el.latestSlidesList.innerHTML = "";
}

function clearSelectedRunOutput() {
  renderDownloadLinks(el.runDownloads, null);
  el.runSlidesList.innerHTML = "";
}

function renderRunsList(runs) {
  if (!el.runsList) return;
  el.runsList.innerHTML = "";
  if (!runs.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "No runs yet.";
    el.runsList.appendChild(empty);
    return;
  }

  for (const run of runs) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "run-card";
    button.classList.toggle("active", run.id === state.selectedRunId);

    const head = document.createElement("div");
    head.className = "run-card-head";

    const title = document.createElement("div");
    title.className = "run-card-title";
    title.textContent = formatRunIdLabel(run.id);
    title.title = run.id;
    head.appendChild(title);

    const badge = document.createElement("span");
    badge.className = `run-card-badge is-${run.run_status || "idle"}`;
    badge.textContent = run.run_status || "idle";
    head.appendChild(badge);

    button.appendChild(head);

    button.addEventListener("click", () => {
      if (state.selectedRunId === run.id) return;
      state.selectedRunId = run.id;
      renderRunsList(runs);
      runTaskImmediateHandler(loadRunDetails);
    });

    el.runsList.appendChild(button);
  }
}

function shouldAutoPreviewLatest(detail) {
  const status = detail?.run_status || "";
  return ["running", "done", "error", "stopped"].includes(status);
}

function deriveLatestAutoPreview(detail) {
  if (!detail) return null;
  if (detail.translated_upscaled_slides_ready) {
    return { slidesMode: "final", sourceMode: "translated" };
  }
  if (detail.upscaled_slides_ready) {
    return { slidesMode: "final", sourceMode: "processed" };
  }
  if (detail.translated_slides_ready) {
    return { slidesMode: "final", sourceMode: "translated" };
  }
  if (detail.final_slides_ready) {
    return { slidesMode: "final", sourceMode: "processed" };
  }
  if (detail.base_events_ready) {
    return { slidesMode: "base", sourceMode: "processed" };
  }
  return null;
}

function applyLatestAutoPreview(detail) {
  const preview = deriveLatestAutoPreview(detail);
  if (!preview) return;
  state.latestSlidesMode = preview.slidesMode;
  el.latestViewMode.value = preview.slidesMode === "base" ? "base" : "final";
  if (preview.slidesMode === "final") {
    state.latestFinalSourceMode = preview.sourceMode;
    el.latestFinalSourceMode.value = preview.sourceMode;
  }
}

async function setFinalSlideImageMode(runId, eventId, mode) {
  await apiPost(`/api/runs/${encodeURIComponent(runId)}/final-slide-image-mode`, {
    event_id: eventId,
    mode,
  });
  const refreshes = [];
  if (runId === state.latestRunId && state.latestSlidesMode === "final") {
    refreshes.push(loadLatestSlides());
  }
  if (runId === state.selectedRunId) {
    refreshes.push(loadRunSlides());
  }
  await Promise.all(refreshes);
}

function resolveRenderedFinalImage(item, slideSourceMode) {
  const wantsRaw = slideSourceMode === "raw";
  const wantsTranslated = slideSourceMode === "translated";

  if (wantsRaw && item.raw_slide_image_url) {
    return { url: item.raw_slide_image_url, name: item.raw_slide_image_name || item.image_name || "", slideSourceLabel: "raw", resolutionLabel: "native" };
  }
  if (wantsTranslated && item.translated_upscaled_slide_image_url) {
    return { url: item.translated_upscaled_slide_image_url, name: item.translated_upscaled_slide_image_name || item.image_name || "", slideSourceLabel: "translated", resolutionLabel: "x4" };
  }
  if (wantsTranslated && item.translated_slide_image_url) {
    return { url: item.translated_slide_image_url, name: item.translated_slide_image_name || item.image_name || "", slideSourceLabel: "translated", resolutionLabel: "native" };
  }
  if (item.processed_upscaled_slide_image_url) {
    return { url: item.processed_upscaled_slide_image_url, name: item.processed_upscaled_slide_image_name || item.image_name || "", slideSourceLabel: "processed", resolutionLabel: "x4" };
  }
  if (item.image_mode === "full") {
    return { url: item.full_image_url || item.image_url || "", name: item.full_image_name || item.image_name || "", slideSourceLabel: wantsTranslated ? "translated" : "processed", resolutionLabel: "native" };
  }
  if (item.processed_slide_image_url) {
    return { url: item.processed_slide_image_url, name: item.processed_slide_image_name || item.image_name || "", slideSourceLabel: "processed", resolutionLabel: "native" };
  }
  if (item.raw_slide_image_url) {
    return { url: item.raw_slide_image_url, name: item.raw_slide_image_name || item.image_name || "", slideSourceLabel: "raw", resolutionLabel: "native" };
  }
  return { url: item.image_url || "", name: item.image_name || "", slideSourceLabel: item.image_mode === "slide" ? "processed" : "-", resolutionLabel: "native" };
}

function resolveRenderedFinalImageStrict(item, sourceLabel, resolutionMode) {
  if (sourceLabel === "raw") {
    if (resolutionMode === "native" && item.raw_slide_image_url) {
      return { url: item.raw_slide_image_url, name: item.raw_slide_image_name || item.image_name || "", slideSourceLabel: "raw", resolutionLabel: "native" };
    }
    return { url: "", name: "", slideSourceLabel: "raw", resolutionLabel: resolutionMode };
  }
  if (sourceLabel === "translated") {
    if (resolutionMode === "native" && item.translated_slide_image_url) {
      return { url: item.translated_slide_image_url, name: item.translated_slide_image_name || item.image_name || "", slideSourceLabel: "translated", resolutionLabel: "native" };
    }
    if (resolutionMode === "native" && item.image_mode === "full" && item.full_image_url) {
      return { url: item.full_image_url, name: item.full_image_name || item.image_name || "", slideSourceLabel: "translated", resolutionLabel: "native" };
    }
    if (resolutionMode === "x4" && item.translated_upscaled_slide_image_url) {
      return { url: item.translated_upscaled_slide_image_url, name: item.translated_upscaled_slide_image_name || item.image_name || "", slideSourceLabel: "translated", resolutionLabel: "x4" };
    }
    return { url: "", name: "", slideSourceLabel: "translated", resolutionLabel: resolutionMode };
  }
  if (resolutionMode === "native" && item.processed_slide_image_url) {
    return { url: item.processed_slide_image_url, name: item.processed_slide_image_name || item.image_name || "", slideSourceLabel: "processed", resolutionLabel: "native" };
  }
  if (resolutionMode === "native" && item.image_mode === "full" && item.full_image_url) {
    return { url: item.full_image_url, name: item.full_image_name || item.image_name || "", slideSourceLabel: "processed", resolutionLabel: "native" };
  }
  if (resolutionMode === "x4" && item.processed_upscaled_slide_image_url) {
    return { url: item.processed_upscaled_slide_image_url, name: item.processed_upscaled_slide_image_name || item.image_name || "", slideSourceLabel: "processed", resolutionLabel: "x4" };
  }
  return { url: "", name: "", slideSourceLabel: "processed", resolutionLabel: resolutionMode };
}

function resolveCompareRenderedImages(item, slideSourceMode) {
  const left = resolveRenderedFinalImageStrict(item, slideSourceMode, "native");
  if (left.slideSourceLabel === "raw") {
    return { left, right: { url: "", name: "", slideSourceLabel: "raw", resolutionLabel: "x4", missingReason: "x4 is not available for raw" } };
  }
  const right = resolveRenderedFinalImageStrict(item, left.slideSourceLabel, "x4");
  if (right.url) return { left, right };
  return { left, right: { ...right, missingReason: `No x4 image available for ${left.slideSourceLabel}` } };
}

function createRenderedImageElement(renderedImage, fallbackName) {
  if (renderedImage.url) {
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = renderedImage.url;
    img.alt = renderedImage.name || fallbackName;
    img.addEventListener("click", () => openImageModal(renderedImage.url, renderedImage.name || fallbackName));
    return img;
  }
  const missing = document.createElement("div");
  missing.className = "slide-missing muted";
  missing.textContent = renderedImage.missingReason || "No image";
  return missing;
}

function createComparePanel(labelText, renderedImage, fallbackName) {
  const panel = document.createElement("div");
  panel.className = "slide-compare-panel";
  const label = document.createElement("div");
  label.className = "slide-compare-label";
  label.textContent = labelText;
  panel.appendChild(label);
  panel.appendChild(createRenderedImageElement(renderedImage, fallbackName));
  return panel;
}

function createImageModeToggle(runId, item) {
  const available = Array.isArray(item.available_image_modes) ? item.available_image_modes : [];
  if (available.length <= 1) return null;
  const wrap = document.createElement("div");
  wrap.className = "slide-controls";
  const label = document.createElement("span");
  label.className = "slide-controls-label";
  label.textContent = "Image:";
  wrap.appendChild(label);
  const toggle = document.createElement("div");
  toggle.className = "mode-toggle";
  for (const mode of [{ key: "slide", label: "ROI" }, { key: "full", label: "Full" }]) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "mode-toggle-btn";
    btn.textContent = mode.label;
    btn.disabled = !available.includes(mode.key);
    btn.classList.toggle("active", item.image_mode === mode.key);
    btn.addEventListener("click", () => runTaskImmediateHandler(() => setFinalSlideImageMode(runId, item.event_id, mode.key)));
    toggle.appendChild(btn);
  }
  wrap.appendChild(toggle);
  return wrap;
}

function createSlideDetailsPanel(facts) {
  const wrap = document.createElement("section");
  wrap.className = "output-info-panel slide-details-panel";
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "output-info-toggle";
  toggle.setAttribute("aria-expanded", "false");
  const title = document.createElement("span");
  title.textContent = "Slide Details";
  const chevron = document.createElement("span");
  chevron.className = "step-section-chevron";
  chevron.setAttribute("aria-hidden", "true");
  toggle.appendChild(title);
  toggle.appendChild(chevron);
  const body = document.createElement("div");
  body.className = "output-info-body";
  body.hidden = true;
  const grid = document.createElement("div");
  grid.className = "output-info-grid";
  for (const [labelText, valueText] of facts) {
    const item = document.createElement("div");
    item.className = "output-info-item";
    const label = document.createElement("div");
    label.className = "output-info-label";
    label.textContent = labelText;
    const value = document.createElement("div");
    value.className = "output-info-value";
    value.textContent = valueText;
    item.appendChild(label);
    item.appendChild(value);
    grid.appendChild(item);
  }
  body.appendChild(grid);
  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", expanded ? "false" : "true");
    body.hidden = expanded;
    wrap.classList.toggle("is-open", !expanded);
  });
  wrap.appendChild(toggle);
  wrap.appendChild(body);
  return wrap;
}

async function renderFinalSlides(runId, target, slideSourceMode, displayMode) {
  if (!runId) {
    target.innerHTML = "";
    return;
  }
  const data = await apiGet(`/api/runs/${encodeURIComponent(runId)}/final-slides`);
  const items = data.items || [];
  target.innerHTML = "";
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "No final slide text map available for this run.";
    target.appendChild(empty);
    return;
  }
  for (const item of items) {
    const row = document.createElement("article");
    row.className = "slide-row";
    const media = document.createElement("div");
    media.className = "slide-media";
    const fallbackName = `event_${item.event_id}`;
    let detailsFacts = [];
    if (displayMode === "compare") {
      const compare = resolveCompareRenderedImages(item, slideSourceMode);
      const compareGrid = document.createElement("div");
      compareGrid.className = "slide-compare-grid";
      compareGrid.appendChild(createComparePanel(`${compare.left.slideSourceLabel} | native`, compare.left, fallbackName));
      compareGrid.appendChild(createComparePanel(`${compare.left.slideSourceLabel} | x4`, compare.right, fallbackName));
      media.appendChild(compareGrid);
      detailsFacts = [
        ["Event", String(item.event_id)],
        ["Start", `${Number(item.slide_start).toFixed(2)}s`],
        ["End", `${Number(item.slide_end).toFixed(2)}s`],
        ["Image", item.image_mode || "-"],
        ["Final Source", item.source_mode_final || "-"],
        ["ROI Source", compare.left.slideSourceLabel],
        ["Display", "compare"],
      ];
    } else {
      const renderedImage = resolveRenderedFinalImage(item, slideSourceMode);
      media.appendChild(createRenderedImageElement(renderedImage, fallbackName));
      detailsFacts = [
        ["Event", String(item.event_id)],
        ["Start", `${Number(item.slide_start).toFixed(2)}s`],
        ["End", `${Number(item.slide_end).toFixed(2)}s`],
        ["Image", item.image_mode || "-"],
        ["Final Source", item.source_mode_final || "-"],
        ["ROI Source", renderedImage.slideSourceLabel],
        ["Resolution", renderedImage.resolutionLabel],
      ];
    }
    const controls = createImageModeToggle(runId, item);
    if (controls) media.appendChild(controls);
    media.appendChild(createSlideDetailsPanel(detailsFacts));
    const textWrap = document.createElement("div");
    textWrap.className = "slide-text";
    textWrap.textContent = item.translated_text || item.text || "(no text)";
    row.appendChild(media);
    row.appendChild(textWrap);
    target.appendChild(row);
  }
}

async function renderBaseEvents(runId, target) {
  if (!runId) {
    target.innerHTML = "";
    return;
  }
  const data = await apiGet(`/api/runs/${encodeURIComponent(runId)}/base-events`);
  const items = data.items || [];
  target.innerHTML = "";
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "No base events available for this run.";
    target.appendChild(empty);
    return;
  }
  for (const item of items) {
    const row = document.createElement("article");
    row.className = "slide-row";
    const media = document.createElement("div");
    media.className = "slide-media";
    if (item.image_url) {
      const img = document.createElement("img");
      img.loading = "lazy";
      img.src = item.image_url;
      img.alt = item.image_name || `event_${item.event_id}`;
      img.addEventListener("click", () => openImageModal(item.image_url, item.image_name || `event_${item.event_id}`));
      media.appendChild(img);
    } else {
      const missing = document.createElement("div");
      missing.className = "slide-missing muted";
      missing.textContent = "No image";
      media.appendChild(missing);
    }
    media.appendChild(createSlideDetailsPanel([
      ["Event", String(item.event_id)],
      ["Time", `${Number(item.time_sec).toFixed(2)}s`],
      ["Frame", String(item.event_frame)],
    ]));
    const info = document.createElement("div");
    info.className = "slide-text";
    info.textContent = `timecode: ${item.timecode || ""}\ntransition_no: ${item.transition_no}\nframe_id_0: ${item.frame_id_0}\nframe_id_1: ${item.frame_id_1}`;
    row.appendChild(media);
    row.appendChild(info);
    target.appendChild(row);
  }
}

export async function loadLatestSlides() {
  const runId = state.latestRunId;
  if (!runId) {
    el.latestSlidesList.innerHTML = "";
    return;
  }
  if (shouldAutoPreviewLatest(state.latestRunDetail)) {
    applyLatestAutoPreview(state.latestRunDetail);
  }
  if (state.latestSlidesMode === "base") {
    await renderBaseEvents(runId, el.latestSlidesList);
    return;
  }
  await renderFinalSlides(runId, el.latestSlidesList, state.latestFinalSourceMode, state.latestFinalDisplayMode);
}

export async function loadRunSlides() {
  const runId = state.selectedRunId;
  if (!runId) {
    el.runSlidesList.innerHTML = "";
    return;
  }
  if (state.runSlidesMode === "base") {
    await renderBaseEvents(runId, el.runSlidesList);
    return;
  }
  await renderFinalSlides(runId, el.runSlidesList, state.runFinalSourceMode, state.runFinalDisplayMode);
}

export async function loadRunDetails() {
  const runId = state.selectedRunId;
  if (!runId) return;
  state.selectedRunId = runId;
  const detail = await apiGet(`/api/runs/${encodeURIComponent(runId)}`);
  renderDownloadLinks(el.runDownloads, detail);
  await loadRunSlides();
}

export async function loadLatestRunDetails() {
  const runId = state.latestRunId;
  if (!runId) {
    state.latestRunDetail = null;
    clearLatestOutput();
    return;
  }
  const detail = await apiGet(`/api/runs/${encodeURIComponent(runId)}`);
  state.latestRunDetail = detail;
  renderLatestInfo(detail);
  renderDownloadLinks(el.latestDownloads, detail, { includeVideo: false, includeNonVideo: true });
  renderDownloadLinks(el.latestExports, detail, { includeVideo: true, includeNonVideo: false });
}

export async function loadRuns() {
  const data = await apiGet("/api/runs");
  const current = data.current || {};
  setStatusHandler(current);
  const currentSettledKey = settledRefreshKey(current);
  if (currentSettledKey) {
    state.lastSettledRefreshKey = currentSettledKey;
  }
  const runs = data.runs || [];
  state.latestRunId = preferredLatestRunId(runs, current);
  const prev = state.selectedRunId;
  if (runs.length === 0) {
    state.selectedRunId = null;
    state.latestRunDetail = null;
    clearLatestOutput();
    clearSelectedRunOutput();
    return;
  }
  const fallback = runs[0].id;
  state.selectedRunId = runs.some((r) => r.id === prev) ? prev : fallback;
  renderRunsList(runs);
  await loadLatestRunDetails();
  await loadLatestSlides();
  await loadRunDetails();
}

function settledRefreshKey(current) {
  const status = current?.status || "";
  if (!["done", "error", "stopped"].includes(status)) return "";
  const runId = current?.run_id || "";
  const finishedAt = current?.finished_at || "";
  const exitCode = current?.exit_code ?? "";
  return `${status}|${runId}|${finishedAt}|${exitCode}`;
}

export async function startRun() {
  await apiPost("/api/runs", {});
  await loadRuns();
}

export async function stopRun() {
  await apiPost("/api/runs/stop", {});
  const current = await apiGet("/api/runs/current");
  setStatusHandler(current);
}

export async function pollCurrent() {
  try {
    const current = await apiGet("/api/runs/current");
    setStatusHandler(current);
    if (current.run_id && ["running", "stopping"].includes(current.status || "")) {
      state.latestRunId = current.run_id;
      await loadLatestRunDetails();
      await loadLatestSlides();
    }
    const key = settledRefreshKey(current);
    if (key && key !== state.lastSettledRefreshKey) {
      state.lastSettledRefreshKey = key;
      await loadRuns();
    }
  } catch (err) {
    console.error(err);
  }
}
