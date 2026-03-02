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
  finalSourceModeAuto: document.getElementById("final_source_mode_auto"),
  fullslideSampleFrames: document.getElementById("fullslide_sample_frames"),
  fullslideBorderStripPx: document.getElementById("fullslide_border_strip_px"),
  fullslideMinMatchedSides: document.getElementById("fullslide_min_matched_sides"),
  fullslideBorderDiffThreshold: document.getElementById("fullslide_border_diff_threshold"),
  fullslidePersonBoxAreaRatio: document.getElementById("fullslide_person_box_area_ratio"),
  fullslidePersonOutsideRatio: document.getElementById("fullslide_person_outside_ratio"),
  keyframeSettleFrames: document.getElementById("keyframe_settle_frames"),
  keyframeStableEndGuardFrames: document.getElementById("keyframe_stable_end_guard_frames"),
  keyframeStableLookaheadFrames: document.getElementById("keyframe_stable_lookahead_frames"),
  speakerFilterMinStage1VideoRatio: document.getElementById("speaker_filter_min_stage1_video_ratio"),
  speakerFilterMaxEdgeDensity: document.getElementById("speaker_filter_max_edge_density"),
  speakerFilterMaxLaplacianVar: document.getElementById("speaker_filter_max_laplacian_var"),
  speakerFilterMaxDurationSec: document.getElementById("speaker_filter_max_duration_sec"),
  finalSlidePostprocessMode: document.getElementById("final_slide_postprocess_mode"),
  geminiEditModel: document.getElementById("gemini_edit_model"),
  geminiEditPrompt: document.getElementById("gemini_edit_prompt"),
  finalSlideTranslationMode: document.getElementById("final_slide_translation_mode"),
  finalSlideTargetLanguage: document.getElementById("final_slide_target_language"),
  geminiTranslateModel: document.getElementById("gemini_translate_model"),
  geminiTranslatePrompt: document.getElementById("gemini_translate_prompt"),
  finalSlideUpscaleMode: document.getElementById("final_slide_upscale_mode"),
  finalSlideUpscaleModel: document.getElementById("final_slide_upscale_model"),
  finalSlideUpscaleDevice: document.getElementById("final_slide_upscale_device"),
  finalSlideUpscaleTileSize: document.getElementById("final_slide_upscale_tile_size"),
  finalSlideUpscaleTileOverlap: document.getElementById("final_slide_upscale_tile_overlap"),
  overlayTime: document.getElementById("overlay-time"),
  regenOverlay: document.getElementById("regen-overlay"),
  refreshOverlay: document.getElementById("refresh-overlay"),
  overlayImage: document.getElementById("overlay-image"),
  overlayLog: document.getElementById("overlay-log"),
  startRun: document.getElementById("start-run"),
  refreshRuns: document.getElementById("refresh-runs"),
  pickVideo: document.getElementById("pick-video"),
  selectedVideoPath: document.getElementById("selected-video-path"),
  selectedVideoThumb: document.getElementById("selected-video-thumb"),
  runLog: document.getElementById("run-log"),
  latestSummary: document.getElementById("latest-summary"),
  latestViewMode: document.getElementById("latest-view-mode"),
  latestFinalSourceMode: document.getElementById("latest-final-source-mode"),
  latestFinalDisplayMode: document.getElementById("latest-final-display-mode"),
  latestFinalResolutionMode: document.getElementById("latest-final-resolution-mode"),
  toggleLatestCsvTable: document.getElementById("toggle-latest-csv-table"),
  latestCsvTableWrap: document.getElementById("latest-csv-table-wrap"),
  latestCsvTable: document.getElementById("latest-csv-table"),
  latestSlidesList: document.getElementById("latest-slides-list"),
  runSelect: document.getElementById("run-select"),
  runFinalSourceMode: document.getElementById("run-final-source-mode"),
  runFinalDisplayMode: document.getElementById("run-final-display-mode"),
  runFinalResolutionMode: document.getElementById("run-final-resolution-mode"),
  runSummary: document.getElementById("run-summary"),
  csvPreview: document.getElementById("csv-preview"),
  runSlidesList: document.getElementById("run-slides-list"),
  imageModal: document.getElementById("image-modal"),
  imageModalBackdrop: document.getElementById("image-modal-backdrop"),
  imageModalClose: document.getElementById("image-modal-close"),
  imageModalImg: document.getElementById("image-modal-img"),
  imageModalCaption: document.getElementById("image-modal-caption"),
  videoPickerModal: document.getElementById("video-picker-modal"),
  videoPickerBackdrop: document.getElementById("video-picker-backdrop"),
  videoPickerClose: document.getElementById("video-picker-close"),
  videoPickerList: document.getElementById("video-picker-list"),
};

const state = {
  selectedRunId: null,
  latestRunId: null,
  selectedVideoPath: "",
  videoItems: [],
  latestCsvLines: [],
  latestCsvExpanded: false,
  latestSlidesMode: "final",
  latestFinalSourceMode: "processed",
  latestFinalDisplayMode: "single",
  latestFinalResolutionMode: "native",
  runFinalSourceMode: "processed",
  runFinalDisplayMode: "single",
  runFinalResolutionMode: "native",
  lastSettledRefreshKey: "",
  currentRunStatus: "idle",
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
  state.currentRunStatus = status;
  const runId = current.run_id ? `, run ${current.run_id}` : "";
  el.status.textContent = `status: ${status}${runId}`;
  syncActionState();

  const logs = (current.log_tail || []).slice(-120);
  const nextLog = logs.join("\n");
  if (el.runLog.textContent !== nextLog) {
    el.runLog.textContent = nextLog;
    // Always keep newest lines visible while the run is progressing.
    el.runLog.scrollTop = el.runLog.scrollHeight;
  }
}

function settledRefreshKey(current) {
  const status = current?.status || "";
  if (status !== "done" && status !== "error") return "";
  const runId = current?.run_id || "";
  const finishedAt = current?.finished_at || "";
  const exitCode = current?.exit_code ?? "";
  return `${status}|${runId}|${finishedAt}|${exitCode}`;
}

function videoThumbUrl(videoPath) {
  return `/api/videos/thumbnail?path=${encodeURIComponent(videoPath)}&v=${Date.now()}`;
}

function syncActionState() {
  const hasVideo = Boolean((state.selectedVideoPath || "").trim());
  el.startRun.disabled = state.currentRunStatus === "running" || !hasVideo;
  el.regenOverlay.disabled = !hasVideo;
}

function renderSelectedVideo() {
  const path = state.selectedVideoPath || "";
  el.selectedVideoPath.textContent = path ? `VIDEO_PATH: ${path}` : "VIDEO_PATH: (nicht gesetzt)";
  if (!path) {
    el.selectedVideoThumb.removeAttribute("src");
    syncActionState();
    return;
  }
  el.selectedVideoThumb.src = videoThumbUrl(path);
  syncActionState();
}

function setConfig(cfg) {
  state.selectedVideoPath = cfg.VIDEO_PATH || "";
  el.roiX0.value = cfg.ROI_X0;
  el.roiY0.value = cfg.ROI_Y0;
  el.roiX1.value = cfg.ROI_X1;
  el.roiY1.value = cfg.ROI_Y1;
  el.finalSourceModeAuto.value = cfg.FINAL_SOURCE_MODE_AUTO || "auto";
  el.fullslideSampleFrames.value = cfg.FULLSLIDE_SAMPLE_FRAMES ?? 3;
  el.fullslideBorderStripPx.value = cfg.FULLSLIDE_BORDER_STRIP_PX ?? 24;
  el.fullslideMinMatchedSides.value = cfg.FULLSLIDE_MIN_MATCHED_SIDES ?? 2;
  el.fullslideBorderDiffThreshold.value = cfg.FULLSLIDE_BORDER_DIFF_THRESHOLD ?? 16.0;
  el.fullslidePersonBoxAreaRatio.value = cfg.FULLSLIDE_PERSON_BOX_AREA_RATIO ?? 0.02;
  el.fullslidePersonOutsideRatio.value = cfg.FULLSLIDE_PERSON_OUTSIDE_RATIO ?? 0.35;
  el.keyframeSettleFrames.value = cfg.KEYFRAME_SETTLE_FRAMES;
  el.keyframeStableEndGuardFrames.value = cfg.KEYFRAME_STABLE_END_GUARD_FRAMES;
  el.keyframeStableLookaheadFrames.value = cfg.KEYFRAME_STABLE_LOOKAHEAD_FRAMES;
  el.speakerFilterMinStage1VideoRatio.value = cfg.SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO;
  el.speakerFilterMaxEdgeDensity.value = cfg.SPEAKER_FILTER_MAX_EDGE_DENSITY;
  el.speakerFilterMaxLaplacianVar.value = cfg.SPEAKER_FILTER_MAX_LAPLACIAN_VAR;
  el.speakerFilterMaxDurationSec.value = cfg.SPEAKER_FILTER_MAX_DURATION_SEC;
  el.finalSlidePostprocessMode.value = cfg.FINAL_SLIDE_POSTPROCESS_MODE || "local";
  el.geminiEditModel.value = cfg.GEMINI_EDIT_MODEL || "gemini-3-pro-image-preview";
  el.geminiEditPrompt.value = cfg.GEMINI_EDIT_PROMPT || "";
  el.finalSlideTranslationMode.value = cfg.FINAL_SLIDE_TRANSLATION_MODE || "none";
  el.finalSlideTargetLanguage.value = cfg.FINAL_SLIDE_TARGET_LANGUAGE || "German";
  el.geminiTranslateModel.value = cfg.GEMINI_TRANSLATE_MODEL || "gemini-3-pro-image-preview";
  el.geminiTranslatePrompt.value = cfg.GEMINI_TRANSLATE_PROMPT || "";
  el.finalSlideUpscaleMode.value = cfg.FINAL_SLIDE_UPSCALE_MODE || "none";
  el.finalSlideUpscaleModel.value = cfg.FINAL_SLIDE_UPSCALE_MODEL || "caidas/swin2SR-classical-sr-x4-64";
  el.finalSlideUpscaleDevice.value = cfg.FINAL_SLIDE_UPSCALE_DEVICE || "auto";
  el.finalSlideUpscaleTileSize.value = cfg.FINAL_SLIDE_UPSCALE_TILE_SIZE ?? 256;
  el.finalSlideUpscaleTileOverlap.value = cfg.FINAL_SLIDE_UPSCALE_TILE_OVERLAP ?? 24;
  const videoLabel = cfg.VIDEO_PATH || "(nicht gesetzt)";
  const geminiState = cfg.GEMINI_API_KEY_SET ? "set" : "missing";
  el.configMeta.textContent = `VIDEO_PATH: ${videoLabel} | source_auto: ${cfg.FINAL_SOURCE_MODE_AUTO} | settle: ${cfg.KEYFRAME_SETTLE_FRAMES} | end_guard: ${cfg.KEYFRAME_STABLE_END_GUARD_FRAMES} | lookahead: ${cfg.KEYFRAME_STABLE_LOOKAHEAD_FRAMES} | speaker_ratio: ${cfg.SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO} | final_mode: ${cfg.FINAL_SLIDE_POSTPROCESS_MODE} | translate_mode: ${cfg.FINAL_SLIDE_TRANSLATION_MODE} | target_lang: ${cfg.FINAL_SLIDE_TARGET_LANGUAGE} | upscale_mode: ${cfg.FINAL_SLIDE_UPSCALE_MODE} | gemini_key: ${geminiState}`;
  renderSelectedVideo();
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
  const videoPath = (state.selectedVideoPath || "").trim();
  if (!videoPath) {
    throw new Error("Bitte zuerst ein Video auswählen.");
  }
  const payload = {
    VIDEO_PATH: videoPath,
    ROI_X0: Number(el.roiX0.value),
    ROI_Y0: Number(el.roiY0.value),
    ROI_X1: Number(el.roiX1.value),
    ROI_Y1: Number(el.roiY1.value),
    FINAL_SOURCE_MODE_AUTO: el.finalSourceModeAuto.value,
    FULLSLIDE_SAMPLE_FRAMES: Number(el.fullslideSampleFrames.value),
    FULLSLIDE_BORDER_STRIP_PX: Number(el.fullslideBorderStripPx.value),
    FULLSLIDE_MIN_MATCHED_SIDES: Number(el.fullslideMinMatchedSides.value),
    FULLSLIDE_BORDER_DIFF_THRESHOLD: Number(el.fullslideBorderDiffThreshold.value),
    FULLSLIDE_PERSON_BOX_AREA_RATIO: Number(el.fullslidePersonBoxAreaRatio.value),
    FULLSLIDE_PERSON_OUTSIDE_RATIO: Number(el.fullslidePersonOutsideRatio.value),
    KEYFRAME_SETTLE_FRAMES: Number(el.keyframeSettleFrames.value),
    KEYFRAME_STABLE_END_GUARD_FRAMES: Number(el.keyframeStableEndGuardFrames.value),
    KEYFRAME_STABLE_LOOKAHEAD_FRAMES: Number(el.keyframeStableLookaheadFrames.value),
    SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO: Number(el.speakerFilterMinStage1VideoRatio.value),
    SPEAKER_FILTER_MAX_EDGE_DENSITY: Number(el.speakerFilterMaxEdgeDensity.value),
    SPEAKER_FILTER_MAX_LAPLACIAN_VAR: Number(el.speakerFilterMaxLaplacianVar.value),
    SPEAKER_FILTER_MAX_DURATION_SEC: Number(el.speakerFilterMaxDurationSec.value),
    FINAL_SLIDE_POSTPROCESS_MODE: el.finalSlidePostprocessMode.value,
    GEMINI_EDIT_MODEL: el.geminiEditModel.value.trim(),
    GEMINI_EDIT_PROMPT: el.geminiEditPrompt.value,
    FINAL_SLIDE_TRANSLATION_MODE: el.finalSlideTranslationMode.value,
    FINAL_SLIDE_TARGET_LANGUAGE: el.finalSlideTargetLanguage.value.trim(),
    GEMINI_TRANSLATE_MODEL: el.geminiTranslateModel.value.trim(),
    GEMINI_TRANSLATE_PROMPT: el.geminiTranslatePrompt.value,
    FINAL_SLIDE_UPSCALE_MODE: el.finalSlideUpscaleMode.value,
    FINAL_SLIDE_UPSCALE_MODEL: el.finalSlideUpscaleModel.value.trim(),
    FINAL_SLIDE_UPSCALE_DEVICE: el.finalSlideUpscaleDevice.value,
    FINAL_SLIDE_UPSCALE_TILE_SIZE: Number(el.finalSlideUpscaleTileSize.value),
    FINAL_SLIDE_UPSCALE_TILE_OVERLAP: Number(el.finalSlideUpscaleTileOverlap.value),
  };
  await apiPost("/api/config", payload);
  await loadConfig();
}

function closeVideoPicker() {
  el.videoPickerModal.classList.remove("open");
  el.videoPickerModal.setAttribute("aria-hidden", "true");
}

function renderVideoPickerList() {
  const items = state.videoItems || [];
  el.videoPickerList.innerHTML = "";
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "Keine Videos unter videos/ gefunden.";
    el.videoPickerList.appendChild(empty);
    return;
  }

  for (const item of items) {
    if (item.type === "dir") {
      const dir = document.createElement("div");
      dir.className = "video-item video-dir";
      dir.style.paddingLeft = `${item.depth * 18}px`;
      dir.textContent = `[dir] ${item.path}`;
      el.videoPickerList.appendChild(dir);
      continue;
    }

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "video-item video-file";
    btn.style.paddingLeft = `${item.depth * 18 + 8}px`;
    btn.textContent = item.path;
    if (item.path === state.selectedVideoPath) {
      btn.classList.add("selected");
    }
    btn.addEventListener("click", () => runTask(async () => {
      state.selectedVideoPath = item.path;
      await saveConfig();
      closeVideoPicker();
    }));
    el.videoPickerList.appendChild(btn);
  }
}

async function openVideoPicker() {
  const data = await apiGet("/api/videos");
  state.videoItems = data.items || [];
  if (data.selected_video) {
    state.selectedVideoPath = data.selected_video;
  }
  renderVideoPickerList();
  el.videoPickerModal.classList.add("open");
  el.videoPickerModal.setAttribute("aria-hidden", "false");
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
  state.latestCsvLines = [];
  state.latestCsvExpanded = false;
  el.latestCsvTable.innerHTML = "";
  el.latestCsvTableWrap.classList.add("hidden");
  el.toggleLatestCsvTable.disabled = true;
  el.toggleLatestCsvTable.textContent = "CSV-Tabelle anzeigen";
  el.latestSlidesList.innerHTML = "";
}

function clearSelectedRunOutput() {
  el.runSummary.textContent = "No runs yet";
  el.csvPreview.textContent = "";
  el.runSlidesList.innerHTML = "";
}

function renderRunSelect(runs) {
  el.runSelect.innerHTML = "";
  for (const run of runs) {
    const opt = document.createElement("option");
    opt.value = run.id;
    opt.textContent = `${run.id} | base ${run.event_count} | final ${run.final_event_count} | final_img ${run.final_slide_images} | translated ${run.translated_slide_images || 0} | x4 ${run.upscaled_slide_images || 0} | translated_x4 ${run.translated_upscaled_slide_images || 0}`;
    el.runSelect.appendChild(opt);
  }
}

async function loadRuns() {
  const data = await apiGet("/api/runs");
  const current = data.current || {};
  setStatus(current);
  const currentSettledKey = settledRefreshKey(current);
  if (currentSettledKey) {
    state.lastSettledRefreshKey = currentSettledKey;
  }

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
  await loadLatestSlides();
  await loadRunDetails();
}

async function loadRunDetails() {
  const runId = el.runSelect.value;
  if (!runId) return;
  state.selectedRunId = runId;

  const detail = await apiGet(`/api/runs/${encodeURIComponent(runId)}`);
  el.runSummary.textContent = `run=${detail.id} | base_events=${detail.event_count} | final_events=${detail.final_event_count} | final_slide_images=${detail.final_slide_images} | translated_slide_images=${detail.translated_slide_images || 0} | upscaled_slide_images=${detail.upscaled_slide_images || 0} | translated_upscaled_slide_images=${detail.translated_upscaled_slide_images || 0}`;
  el.csvPreview.textContent = (detail.final_csv_preview || detail.csv_preview || []).join("\n");
  await loadRunSlides();
}

async function loadLatestRunDetails() {
  const runId = state.latestRunId;
  if (!runId) {
    clearLatestOutput();
    return;
  }

  const detail = await apiGet(`/api/runs/${encodeURIComponent(runId)}`);
  el.latestSummary.textContent = `latest=${detail.id} | base_events=${detail.event_count} | final_events=${detail.final_event_count} | final_slide_images=${detail.final_slide_images} | translated_slide_images=${detail.translated_slide_images || 0} | upscaled_slide_images=${detail.upscaled_slide_images || 0} | translated_upscaled_slide_images=${detail.translated_upscaled_slide_images || 0}`;
  state.latestCsvLines = detail.final_csv_preview || detail.csv_preview || [];
  const hasCsv = state.latestCsvLines.length > 0;
  el.toggleLatestCsvTable.disabled = !hasCsv;
  if (!hasCsv) {
    state.latestCsvExpanded = false;
    el.latestCsvTable.innerHTML = "";
    el.latestCsvTableWrap.classList.add("hidden");
    el.toggleLatestCsvTable.textContent = "CSV-Tabelle anzeigen";
    return;
  }
  if (state.latestCsvExpanded) {
    buildLatestCsvTable();
    el.latestCsvTableWrap.classList.remove("hidden");
    el.toggleLatestCsvTable.textContent = "CSV-Tabelle ausblenden";
  } else {
    el.latestCsvTable.innerHTML = "";
    el.latestCsvTableWrap.classList.add("hidden");
    el.toggleLatestCsvTable.textContent = "CSV-Tabelle anzeigen";
  }
}

function parseCsvLine(line) {
  const cells = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === "\"") {
      if (inQuotes && line[i + 1] === "\"") {
        cur += "\"";
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      cells.push(cur);
      cur = "";
      continue;
    }
    cur += ch;
  }
  cells.push(cur);
  return cells;
}

function buildLatestCsvTable() {
  const lines = state.latestCsvLines || [];
  el.latestCsvTable.innerHTML = "";
  if (lines.length === 0) return;

  const rows = lines.map((line) => parseCsvLine(line));
  const colCount = rows.reduce((max, row) => Math.max(max, row.length), 0);
  if (colCount === 0) return;

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  const headers = rows[0] || [];
  for (let i = 0; i < colCount; i += 1) {
    const th = document.createElement("th");
    th.textContent = headers[i] || `column_${i + 1}`;
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);
  el.latestCsvTable.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const row of rows.slice(1)) {
    const tr = document.createElement("tr");
    for (let i = 0; i < colCount; i += 1) {
      const td = document.createElement("td");
      td.textContent = row[i] || "";
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  el.latestCsvTable.appendChild(tbody);
}

function toggleLatestCsvTable() {
  if (state.latestCsvExpanded) {
    state.latestCsvExpanded = false;
    el.latestCsvTableWrap.classList.add("hidden");
    el.toggleLatestCsvTable.textContent = "CSV-Tabelle anzeigen";
    return;
  }
  if ((state.latestCsvLines || []).length === 0) return;

  buildLatestCsvTable();
  state.latestCsvExpanded = true;
  el.latestCsvTableWrap.classList.remove("hidden");
  el.toggleLatestCsvTable.textContent = "CSV-Tabelle ausblenden";
}

function syncFinalViewControls() {
  el.latestFinalResolutionMode.disabled = state.latestFinalDisplayMode === "compare";
  el.runFinalResolutionMode.disabled = state.runFinalDisplayMode === "compare";
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

function resolveRenderedFinalImage(item, slideSourceMode, resolutionMode) {
  const wantsRaw = slideSourceMode === "raw";
  const wantsTranslated = slideSourceMode === "translated";
  const wantsX4 = resolutionMode === "x4";

  if (item.image_mode === "full") {
    return {
      url: item.full_image_url || item.image_url || "",
      name: item.full_image_name || item.image_name || "",
      slideSourceLabel: "full",
      resolutionLabel: "native",
    };
  }

  if (wantsRaw && item.raw_slide_image_url) {
    return {
      url: item.raw_slide_image_url,
      name: item.raw_slide_image_name || item.image_name || "",
      slideSourceLabel: "raw",
      resolutionLabel: "native",
    };
  }

  if (wantsTranslated && wantsX4 && item.translated_upscaled_slide_image_url) {
    return {
      url: item.translated_upscaled_slide_image_url,
      name: item.translated_upscaled_slide_image_name || item.image_name || "",
      slideSourceLabel: "translated",
      resolutionLabel: "x4",
    };
  }

  if (wantsTranslated && item.translated_slide_image_url) {
    return {
      url: item.translated_slide_image_url,
      name: item.translated_slide_image_name || item.image_name || "",
      slideSourceLabel: "translated",
      resolutionLabel: "native",
    };
  }

  if (wantsX4 && item.processed_upscaled_slide_image_url) {
    return {
      url: item.processed_upscaled_slide_image_url,
      name: item.processed_upscaled_slide_image_name || item.image_name || "",
      slideSourceLabel: "processed",
      resolutionLabel: "x4",
    };
  }

  if (item.processed_slide_image_url) {
    return {
      url: item.processed_slide_image_url,
      name: item.processed_slide_image_name || item.image_name || "",
      slideSourceLabel: "processed",
      resolutionLabel: "native",
    };
  }

  if (item.raw_slide_image_url) {
    return {
      url: item.raw_slide_image_url,
      name: item.raw_slide_image_name || item.image_name || "",
      slideSourceLabel: "raw",
      resolutionLabel: "native",
    };
  }

  return {
    url: item.image_url || "",
    name: item.image_name || "",
    slideSourceLabel: item.image_mode === "slide" ? "processed" : "-",
    resolutionLabel: "native",
  };
}

function resolveRenderedFinalImageStrict(item, sourceLabel, resolutionMode) {
  if (sourceLabel === "full") {
    return {
      url: "",
      name: "",
      slideSourceLabel: "full",
      resolutionLabel,
    };
  }
  if (sourceLabel === "raw") {
    if (resolutionMode === "native" && item.raw_slide_image_url) {
      return {
        url: item.raw_slide_image_url,
        name: item.raw_slide_image_name || item.image_name || "",
        slideSourceLabel: "raw",
        resolutionLabel: "native",
      };
    }
    return {
      url: "",
      name: "",
      slideSourceLabel: "raw",
      resolutionLabel,
    };
  }
  if (sourceLabel === "translated") {
    if (resolutionMode === "native" && item.translated_slide_image_url) {
      return {
        url: item.translated_slide_image_url,
        name: item.translated_slide_image_name || item.image_name || "",
        slideSourceLabel: "translated",
        resolutionLabel: "native",
      };
    }
    if (resolutionMode === "x4" && item.translated_upscaled_slide_image_url) {
      return {
        url: item.translated_upscaled_slide_image_url,
        name: item.translated_upscaled_slide_image_name || item.image_name || "",
        slideSourceLabel: "translated",
        resolutionLabel: "x4",
      };
    }
    return {
      url: "",
      name: "",
      slideSourceLabel: "translated",
      resolutionLabel,
    };
  }
  if (resolutionMode === "native" && item.processed_slide_image_url) {
    return {
      url: item.processed_slide_image_url,
      name: item.processed_slide_image_name || item.image_name || "",
      slideSourceLabel: "processed",
      resolutionLabel: "native",
    };
  }
  if (resolutionMode === "x4" && item.processed_upscaled_slide_image_url) {
    return {
      url: item.processed_upscaled_slide_image_url,
      name: item.processed_upscaled_slide_image_name || item.image_name || "",
      slideSourceLabel: "processed",
      resolutionLabel: "x4",
    };
  }
  return {
    url: "",
    name: "",
    slideSourceLabel: "processed",
    resolutionLabel,
  };
}

function resolveCompareRenderedImages(item, slideSourceMode) {
  const left = resolveRenderedFinalImage(item, slideSourceMode, "native");
  if (left.slideSourceLabel === "full") {
    return {
      left,
      right: {
        url: "",
        name: "",
        slideSourceLabel: "full",
        resolutionLabel: "x4",
        missingReason: "x4 nicht verfügbar für Vollbild",
      },
    };
  }
  if (left.slideSourceLabel === "raw") {
    return {
      left,
      right: {
        url: "",
        name: "",
        slideSourceLabel: "raw",
        resolutionLabel: "x4",
        missingReason: "x4 nicht verfügbar für raw",
      },
    };
  }
  const right = resolveRenderedFinalImageStrict(item, left.slideSourceLabel, "x4");
  if (right.url) {
    return { left, right };
  }
  return {
    left,
    right: {
      ...right,
      missingReason: `Kein x4-Bild für ${left.slideSourceLabel}`,
    },
  };
}

function createRenderedImageElement(renderedImage, fallbackName) {
  if (renderedImage.url) {
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = `${renderedImage.url}?v=${Date.now()}`;
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
  if (available.length <= 1) {
    return null;
  }

  const wrap = document.createElement("div");
  wrap.className = "slide-controls";

  const label = document.createElement("span");
  label.className = "slide-controls-label";
  label.textContent = "Bild:";
  wrap.appendChild(label);

  const toggle = document.createElement("div");
  toggle.className = "mode-toggle";

  const modes = [
    { key: "slide", label: "ROI" },
    { key: "full", label: "Vollbild" },
  ];

  for (const mode of modes) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "mode-toggle-btn";
    btn.textContent = mode.label;
    btn.disabled = !available.includes(mode.key);
    btn.classList.toggle("active", item.image_mode === mode.key);
    btn.addEventListener("click", () => runTaskImmediate(() => setFinalSlideImageMode(runId, item.event_id, mode.key)));
    toggle.appendChild(btn);
  }

  wrap.appendChild(toggle);
  return wrap;
}

async function renderFinalSlides(runId, target, slideSourceMode, resolutionMode, displayMode) {
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
    let metaText = "";

    if (displayMode === "compare") {
      const compare = resolveCompareRenderedImages(item, slideSourceMode);
      const compareGrid = document.createElement("div");
      compareGrid.className = "slide-compare-grid";
      compareGrid.appendChild(
        createComparePanel(
          `${compare.left.slideSourceLabel} | native`,
          compare.left,
          fallbackName,
        ),
      );
      compareGrid.appendChild(
        createComparePanel(
          `${compare.left.slideSourceLabel} | x4`,
          compare.right,
          fallbackName,
        ),
      );
      media.appendChild(compareGrid);
      metaText = `event ${item.event_id} | ${Number(item.slide_start).toFixed(2)}s - ${Number(item.slide_end).toFixed(2)}s | bild: ${item.image_mode || "-"} | final_quelle: ${item.source_mode_final || "-"} | roi_quelle: ${compare.left.slideSourceLabel} | anzeige: compare`;
    } else {
      const renderedImage = resolveRenderedFinalImage(item, slideSourceMode, resolutionMode);
      media.appendChild(createRenderedImageElement(renderedImage, fallbackName));
      metaText = `event ${item.event_id} | ${Number(item.slide_start).toFixed(2)}s - ${Number(item.slide_end).toFixed(2)}s | bild: ${item.image_mode || "-"} | final_quelle: ${item.source_mode_final || "-"} | roi_quelle: ${renderedImage.slideSourceLabel} | auflösung: ${renderedImage.resolutionLabel}`;
    }

    const controls = createImageModeToggle(runId, item);
    if (controls) {
      media.appendChild(controls);
    }

    const meta = document.createElement("div");
    meta.className = "slide-meta";
    meta.textContent = metaText;
    media.appendChild(meta);

    const textWrap = document.createElement("div");
    textWrap.className = "slide-text";
    textWrap.textContent = item.text || "(no text)";

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
      img.src = `${item.image_url}?v=${Date.now()}`;
      img.alt = item.image_name || `event_${item.event_id}`;
      img.addEventListener("click", () => openImageModal(item.image_url, item.image_name || `event_${item.event_id}`));
      media.appendChild(img);
    } else {
      const missing = document.createElement("div");
      missing.className = "slide-missing muted";
      missing.textContent = "No image";
      media.appendChild(missing);
    }

    const meta = document.createElement("div");
    meta.className = "slide-meta";
    meta.textContent = `event ${item.event_id} | ${Number(item.time_sec).toFixed(2)}s | frame ${item.event_frame}`;
    media.appendChild(meta);

    const info = document.createElement("div");
    info.className = "slide-text";
    info.textContent = `timecode: ${item.timecode || ""}\ntransition_no: ${item.transition_no}\nframe_id_0: ${item.frame_id_0}\nframe_id_1: ${item.frame_id_1}`;

    row.appendChild(media);
    row.appendChild(info);
    target.appendChild(row);
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

async function loadLatestSlides() {
  const runId = state.latestRunId;
  if (!runId) {
    el.latestSlidesList.innerHTML = "";
    return;
  }
  if (state.latestSlidesMode === "base") {
    await renderBaseEvents(runId, el.latestSlidesList);
    return;
  }
  await renderFinalSlides(
    runId,
    el.latestSlidesList,
    state.latestFinalSourceMode,
    state.latestFinalResolutionMode,
    state.latestFinalDisplayMode,
  );
}

async function loadRunSlides() {
  const runId = el.runSelect.value;
  if (!runId) {
    el.runSlidesList.innerHTML = "";
    return;
  }
  await renderFinalSlides(
    runId,
    el.runSlidesList,
    state.runFinalSourceMode,
    state.runFinalResolutionMode,
    state.runFinalDisplayMode,
  );
}

async function startRun() {
  await apiPost("/api/runs", {});
  await loadRuns();
}

async function pollCurrent() {
  try {
    const current = await apiGet("/api/runs/current");
    setStatus(current);
    const key = settledRefreshKey(current);
    if (key && key !== state.lastSettledRefreshKey) {
      state.lastSettledRefreshKey = key;
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
  el.pickVideo.addEventListener("click", () => runTask(openVideoPicker));
  el.latestViewMode.addEventListener("change", () => {
    state.latestSlidesMode = el.latestViewMode.value === "base" ? "base" : "final";
    runTaskImmediate(loadLatestSlides);
  });
  el.latestFinalSourceMode.addEventListener("change", () => {
    state.latestFinalSourceMode = ["raw", "translated"].includes(el.latestFinalSourceMode.value)
      ? el.latestFinalSourceMode.value
      : "processed";
    runTaskImmediate(loadLatestSlides);
  });
  el.latestFinalDisplayMode.addEventListener("change", () => {
    state.latestFinalDisplayMode = el.latestFinalDisplayMode.value === "compare" ? "compare" : "single";
    syncFinalViewControls();
    runTaskImmediate(loadLatestSlides);
  });
  el.latestFinalResolutionMode.addEventListener("change", () => {
    state.latestFinalResolutionMode = el.latestFinalResolutionMode.value === "x4" ? "x4" : "native";
    runTaskImmediate(loadLatestSlides);
  });
  el.toggleLatestCsvTable.addEventListener("click", toggleLatestCsvTable);
  el.runSelect.addEventListener("change", () => runTask(loadRunDetails));
  el.runFinalSourceMode.addEventListener("change", () => {
    state.runFinalSourceMode = ["raw", "translated"].includes(el.runFinalSourceMode.value)
      ? el.runFinalSourceMode.value
      : "processed";
    runTaskImmediate(loadRunSlides);
  });
  el.runFinalDisplayMode.addEventListener("change", () => {
    state.runFinalDisplayMode = el.runFinalDisplayMode.value === "compare" ? "compare" : "single";
    syncFinalViewControls();
    runTaskImmediate(loadRunSlides);
  });
  el.runFinalResolutionMode.addEventListener("change", () => {
    state.runFinalResolutionMode = el.runFinalResolutionMode.value === "x4" ? "x4" : "native";
    runTaskImmediate(loadRunSlides);
  });
  el.imageModalClose.addEventListener("click", closeImageModal);
  el.imageModalBackdrop.addEventListener("click", closeImageModal);
  el.videoPickerClose.addEventListener("click", closeVideoPicker);
  el.videoPickerBackdrop.addEventListener("click", closeVideoPicker);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && el.imageModal.classList.contains("open")) {
      closeImageModal();
    }
    if (e.key === "Escape" && el.videoPickerModal.classList.contains("open")) {
      closeVideoPicker();
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
  state.latestSlidesMode = el.latestViewMode.value === "base" ? "base" : "final";
  state.latestFinalSourceMode = ["raw", "translated"].includes(el.latestFinalSourceMode.value)
    ? el.latestFinalSourceMode.value
    : "processed";
  state.latestFinalDisplayMode = el.latestFinalDisplayMode.value === "compare" ? "compare" : "single";
  state.latestFinalResolutionMode = el.latestFinalResolutionMode.value === "x4" ? "x4" : "native";
  state.runFinalSourceMode = ["raw", "translated"].includes(el.runFinalSourceMode.value)
    ? el.runFinalSourceMode.value
    : "processed";
  state.runFinalDisplayMode = el.runFinalDisplayMode.value === "compare" ? "compare" : "single";
  state.runFinalResolutionMode = el.runFinalResolutionMode.value === "x4" ? "x4" : "native";
  syncFinalViewControls();
  setActiveTab("home");
  await runTask(loadConfig);
  await runTask(loadOverlay);
  await runTask(loadRuns);
  setInterval(pollCurrent, 2000);
}

init();
