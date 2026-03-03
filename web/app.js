const el = {
  tabButtons: document.querySelectorAll(".tab-btn"),
  panelHome: document.getElementById("panel-home"),
  panelAllRuns: document.getElementById("panel-all-runs"),
  panelImageLab: document.getElementById("panel-image-lab"),
  panelRoi: document.getElementById("panel-roi"),
  panelSettings: document.getElementById("panel-settings"),
  configMeta: document.getElementById("config-meta"),
  saveRoi: document.getElementById("save-roi"),
  saveSettings: document.getElementById("save-settings"),
  openStatus: document.getElementById("open-status"),
  stopRun: document.getElementById("stop-run"),
  statusSummary: document.getElementById("status-summary"),
  runSteps: document.getElementById("run-steps"),
  roiX0: document.getElementById("roi_x0"),
  roiY0: document.getElementById("roi_y0"),
  roiX1: document.getElementById("roi_x1"),
  roiY1: document.getElementById("roi_y1"),
  runStepEdit: document.getElementById("run_step_edit"),
  runStepTranslate: document.getElementById("run_step_translate"),
  runStepUpscale: document.getElementById("run_step_upscale"),
  runStepTextTranslate: document.getElementById("run_step_text_translate"),
  runStepTts: document.getElementById("run_step_tts"),
  runStepVideoExport: document.getElementById("run_step_video_export"),
  finalSourceModeAuto: document.getElementById("final_source_mode_auto"),
  transcriptionProvider: document.getElementById("transcription_provider"),
  whisperModel: document.getElementById("whisper_model"),
  whisperDevice: document.getElementById("whisper_device"),
  whisperComputeType: document.getElementById("whisper_compute_type"),
  whisperLanguage: document.getElementById("whisper_language"),
  googleSpeechProjectId: document.getElementById("google_speech_project_id"),
  googleSpeechLocation: document.getElementById("google_speech_location"),
  googleSpeechModel: document.getElementById("google_speech_model"),
  googleSpeechLanguageCodes: document.getElementById("google_speech_language_codes"),
  googleSpeechChunkSec: document.getElementById("google_speech_chunk_sec"),
  googleSpeechChunkOverlapSec: document.getElementById("google_speech_chunk_overlap_sec"),
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
  geminiTextTranslateModel: document.getElementById("gemini_text_translate_model"),
  geminiTextTranslatePrompt: document.getElementById("gemini_text_translate_prompt"),
  geminiTtsModel: document.getElementById("gemini_tts_model"),
  geminiTtsVoice: document.getElementById("gemini_tts_voice"),
  googleTtsProjectId: document.getElementById("google_tts_project_id"),
  googleTtsLanguageCode: document.getElementById("google_tts_language_code"),
  ttsLanguageHint: document.getElementById("tts-language-hint"),
  geminiTtsPrompt: document.getElementById("gemini_tts_prompt"),
  ttsHealthCheck: document.getElementById("tts-health-check"),
  ttsHealthStatus: document.getElementById("tts-health-status"),
  ttsHealthMeta: document.getElementById("tts-health-meta"),
  finalSlideUpscaleMode: document.getElementById("final_slide_upscale_mode"),
  finalSlideUpscaleModel: document.getElementById("final_slide_upscale_model"),
  finalSlideUpscaleDevice: document.getElementById("final_slide_upscale_device"),
  finalSlideUpscaleTileSize: document.getElementById("final_slide_upscale_tile_size"),
  finalSlideUpscaleTileOverlap: document.getElementById("final_slide_upscale_tile_overlap"),
  replicateNightmareRealesrganModelRef: document.getElementById("replicate_nightmare_realesrgan_model_ref"),
  replicateNightmareRealesrganVersionId: document.getElementById("replicate_nightmare_realesrgan_version_id"),
  replicateNightmareRealesrganPricePerSecond: document.getElementById("replicate_nightmare_realesrgan_price_per_second"),
  replicateUpscaleConcurrency: document.getElementById("replicate_upscale_concurrency"),
  videoExportMinSlideSec: document.getElementById("video_export_min_slide_sec"),
  videoExportTailPadSec: document.getElementById("video_export_tail_pad_sec"),
  videoExportWidth: document.getElementById("video_export_width"),
  videoExportHeight: document.getElementById("video_export_height"),
  videoExportFps: document.getElementById("video_export_fps"),
  videoExportBgColor: document.getElementById("video_export_bg_color"),
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
  labPickImage: document.getElementById("lab-pick-image"),
  labRunEdit: document.getElementById("lab-run-edit"),
  labRunTranslate: document.getElementById("lab-run-translate"),
  labUpscaleProvider: document.getElementById("lab_upscale_provider"),
  labRunUpscale: document.getElementById("lab-run-upscale"),
  labSelectedImage: document.getElementById("lab-selected-image"),
  labJobStatus: document.getElementById("lab-job-status"),
  labJobMeta: document.getElementById("lab-job-meta"),
  labLog: document.getElementById("lab-log"),
  labOriginalImage: document.getElementById("lab-original-image"),
  labResultImage: document.getElementById("lab-result-image"),
  latestSummary: document.getElementById("latest-summary"),
  latestDownloads: document.getElementById("latest-downloads"),
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
  runDownloads: document.getElementById("run-downloads"),
  csvPreview: document.getElementById("csv-preview"),
  runSlidesList: document.getElementById("run-slides-list"),
  imageModal: document.getElementById("image-modal"),
  imageModalBackdrop: document.getElementById("image-modal-backdrop"),
  imageModalClose: document.getElementById("image-modal-close"),
  imageModalImg: document.getElementById("image-modal-img"),
  imageModalCaption: document.getElementById("image-modal-caption"),
  statusModal: document.getElementById("status-modal"),
  statusModalBackdrop: document.getElementById("status-modal-backdrop"),
  statusModalClose: document.getElementById("status-modal-close"),
  videoPickerModal: document.getElementById("video-picker-modal"),
  videoPickerBackdrop: document.getElementById("video-picker-backdrop"),
  videoPickerClose: document.getElementById("video-picker-close"),
  videoPickerList: document.getElementById("video-picker-list"),
  labImagePickerModal: document.getElementById("lab-image-picker-modal"),
  labImagePickerBackdrop: document.getElementById("lab-image-picker-backdrop"),
  labImagePickerClose: document.getElementById("lab-image-picker-close"),
  labImagePickerList: document.getElementById("lab-image-picker-list"),
};

const state = {
  selectedRunId: null,
  latestRunId: null,
  currentRunId: null,
  selectedVideoPath: "",
  videoItems: [],
  labImages: [],
  labSelectedImage: null,
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
  labStatus: "idle",
  stepSectionExpanded: {},
};

const ACTIVE_TAB_STORAGE_KEY = "slide-transform-active-tab";
const TARGET_LANGUAGE_PREFIX_RULES = [
  { prefixes: ["de"], names: ["german", "deutsch"] },
  { prefixes: ["en"], names: ["english", "englisch"] },
  { prefixes: ["fr"], names: ["french", "francais", "français"] },
  { prefixes: ["es"], names: ["spanish", "espanol", "español"] },
  { prefixes: ["it"], names: ["italian", "italiano"] },
  { prefixes: ["pt"], names: ["portuguese", "portugues", "português"] },
  { prefixes: ["nl"], names: ["dutch", "nederlands"] },
  { prefixes: ["pl"], names: ["polish", "polski"] },
  { prefixes: ["sv"], names: ["swedish", "svenska"] },
  { prefixes: ["da"], names: ["danish", "dansk"] },
  { prefixes: ["nb", "no"], names: ["norwegian", "norsk"] },
  { prefixes: ["fi"], names: ["finnish", "suomi"] },
  { prefixes: ["cs"], names: ["czech", "čeština", "cestina"] },
  { prefixes: ["sk"], names: ["slovak", "slovencina", "slovenčina"] },
  { prefixes: ["ro"], names: ["romanian", "romana", "română", "romana"] },
  { prefixes: ["hu"], names: ["hungarian", "magyar"] },
  { prefixes: ["tr"], names: ["turkish", "turkce", "türkçe"] },
  { prefixes: ["ru"], names: ["russian", "russkiy", "русский"] },
  { prefixes: ["uk"], names: ["ukrainian", "українська", "ukrainska"] },
  { prefixes: ["ja"], names: ["japanese", "nihongo", "日本語"] },
  { prefixes: ["ko"], names: ["korean", "한국어"] },
  { prefixes: ["zh"], names: ["chinese", "mandarin", "中文"] },
  { prefixes: ["ar"], names: ["arabic", "العربية"] },
  { prefixes: ["hi"], names: ["hindi", "हिन्दी", "हिंदी"] },
];

const buttonFeedbackTimers = new WeakMap();

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
  state.currentRunId = current.run_id || null;
  const runId = current.run_id ? `, run ${current.run_id}` : "";
  if (el.statusSummary) {
    el.statusSummary.textContent = `status: ${status}${runId}`;
  }
  renderRunSteps(current);
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
  if (!["done", "error", "stopped"].includes(status)) return "";
  const runId = current?.run_id || "";
  const finishedAt = current?.finished_at || "";
  const exitCode = current?.exit_code ?? "";
  return `${status}|${runId}|${finishedAt}|${exitCode}`;
}

function videoThumbUrl(videoPath) {
  return `/api/videos/thumbnail?path=${encodeURIComponent(videoPath)}&v=${Date.now()}`;
}

function formatUsd(value) {
  const num = Number(value || 0);
  if (!(num > 0)) return "-";
  return `$${num.toFixed(4)}`;
}

function preferredLatestRunId(runs, current) {
  const currentRunId = current?.run_id || "";
  const currentStatus = current?.status || "";
  if (currentRunId && currentStatus && currentStatus !== "idle") {
    return currentRunId;
  }
  return runs.length > 0 ? runs[0].id : null;
}

function buildRunSummary(detail, label = "run") {
  return [
    `${label}=${detail.id}`,
    `run_status=${detail.run_status || "-"}`,
    `available=${detail.highest_available_label || "no output yet"}`,
    `upscale_mode=${detail.upscale_mode_used || "-"}`,
    `upscale_cost=${formatUsd(detail.upscale_estimated_cost_usd)}`,
    `base_events=${detail.event_count}`,
    `final_events=${detail.final_event_count}`,
    `final_slide_images=${detail.final_slide_images}`,
    `translated_slide_images=${detail.translated_slide_images || 0}`,
    `upscaled_slide_images=${detail.upscaled_slide_images || 0}`,
    `translated_upscaled_slide_images=${detail.translated_upscaled_slide_images || 0}`,
    `translated_text_events=${detail.translated_text_events || 0}`,
    `tts_segments=${detail.tts_segments || 0}`,
    `video_export=${detail.exported_video_name || "-"}`,
  ].join(" | ");
}

function isStepSectionEnabled(section) {
  const inputId = section?.dataset?.stepInput || "";
  if (!inputId) return true;
  const input = document.getElementById(inputId);
  return Boolean(input && input.checked);
}

function syncStepSections() {
  const sections = document.querySelectorAll(".step-section[data-step-section]");
  for (const section of sections) {
    const sectionId = section.dataset.stepSection;
    const body = section.querySelector(".step-section-body");
    const toggleBtn = section.querySelector(".step-section-toggle");
    const forced = !section.dataset.stepInput;
    const enabled = isStepSectionEnabled(section);

    if (!(sectionId in state.stepSectionExpanded)) {
      state.stepSectionExpanded[sectionId] = false;
    }

    if (!forced && !enabled) {
      state.stepSectionExpanded[sectionId] = false;
    }

    const expanded = Boolean(state.stepSectionExpanded[sectionId]);
    const showBody = forced ? expanded : enabled && expanded;

    section.classList.toggle("is-forced", forced);
    section.classList.toggle("is-enabled", enabled);
    section.classList.toggle("is-disabled", !enabled);
    section.classList.toggle("is-open", showBody);

    if (body) {
      body.hidden = !showBody;
      body.setAttribute("aria-hidden", showBody ? "false" : "true");
    }

    if (toggleBtn) {
      toggleBtn.disabled = !forced && !enabled;
      toggleBtn.setAttribute("aria-expanded", showBody ? "true" : "false");
      toggleBtn.setAttribute("aria-label", !forced && !enabled ? "Section disabled" : (showBody ? "Collapse settings section" : "Expand settings section"));
    }
  }
}

function renderDownloadLinks(target, detail) {
  if (!target) return;
  target.innerHTML = "";
  if (!detail) return;

  const links = [
    { label: "Translated Text JSON", url: detail.translated_text_json_url, name: "slide_text_map_final_translated.json" },
    { label: "Translated Text CSV", url: detail.translated_text_csv_url, name: "slide_text_map_final_translated.csv" },
    { label: "TTS Manifest", url: detail.tts_manifest_url, name: "tts_manifest.json" },
    { label: "Timeline JSON", url: detail.video_timeline_json_url, name: "timeline.json" },
    { label: "Timeline CSV", url: detail.video_timeline_csv_url, name: "timeline.csv" },
    { label: "Subtitles", url: detail.exported_srt_url, name: detail.exported_video_name ? detail.exported_video_name.replace(/\.mp4$/i, ".srt") : "final.srt" },
    { label: "Exported MP4", url: detail.exported_video_url, name: detail.exported_video_name || "final.mp4" },
  ].filter((item) => item.url);

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

function syncActionState() {
  const hasVideo = Boolean((state.selectedVideoPath || "").trim());
  const isBusyRun = state.currentRunStatus === "running" || state.currentRunStatus === "stopping";
  el.startRun.disabled = isBusyRun || !hasVideo;
  el.regenOverlay.disabled = !hasVideo;
  if (el.stopRun) {
    el.stopRun.disabled = state.currentRunStatus !== "running";
    el.stopRun.textContent = state.currentRunStatus === "stopping" ? "Stopping..." : "Stop Run";
  }
  syncLabActionState();
}

function renderRunSteps(current) {
  const steps = Array.isArray(current?.steps) ? current.steps : [];
  el.runSteps.innerHTML = "";
  if (steps.length === 0) return;

  for (const step of steps) {
    const row = document.createElement("div");
    row.className = `step-item is-${step.status || "pending"}`;

    const icon = document.createElement("span");
    icon.className = `step-icon is-${step.status || "pending"}`;
    icon.setAttribute("aria-hidden", "true");
    row.appendChild(icon);

    const body = document.createElement("div");
    body.className = "step-body";

    const head = document.createElement("div");
    head.className = "step-head";

    const label = document.createElement("span");
    label.className = "step-label";
    label.textContent = step.label || step.id || "Step";
    head.appendChild(label);

    const stateText = document.createElement("span");
    stateText.className = "step-state";
    stateText.textContent = step.status || "pending";
    head.appendChild(stateText);
    body.appendChild(head);

    const detail = document.createElement("div");
    detail.className = "step-detail";
    detail.textContent = step.detail || " ";
    body.appendChild(detail);

    row.appendChild(body);
    el.runSteps.appendChild(row);
  }
}

function openStatusModal() {
  el.statusModal.classList.add("open");
  el.statusModal.setAttribute("aria-hidden", "false");
}

function closeStatusModal() {
  el.statusModal.classList.remove("open");
  el.statusModal.setAttribute("aria-hidden", "true");
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
  el.runStepEdit.checked = Boolean(cfg.RUN_STEP_EDIT);
  el.runStepTranslate.checked = Boolean(cfg.RUN_STEP_TRANSLATE);
  el.runStepUpscale.checked = Boolean(cfg.RUN_STEP_UPSCALE);
  el.runStepTextTranslate.checked = Boolean(cfg.RUN_STEP_TEXT_TRANSLATE);
  el.runStepTts.checked = Boolean(cfg.RUN_STEP_TTS);
  el.runStepVideoExport.checked = Boolean(cfg.RUN_STEP_VIDEO_EXPORT);
  el.finalSourceModeAuto.value = cfg.FINAL_SOURCE_MODE_AUTO || "auto";
  el.transcriptionProvider.value = cfg.TRANSCRIPTION_PROVIDER || "whisper";
  el.whisperModel.value = cfg.WHISPER_MODEL || "medium";
  el.whisperDevice.value = cfg.WHISPER_DEVICE || "cuda";
  el.whisperComputeType.value = cfg.WHISPER_COMPUTE_TYPE || "float16";
  el.whisperLanguage.value = cfg.WHISPER_LANGUAGE || "";
  el.googleSpeechProjectId.value = cfg.GOOGLE_SPEECH_PROJECT_ID || "";
  el.googleSpeechLocation.value = cfg.GOOGLE_SPEECH_LOCATION || "global";
  el.googleSpeechModel.value = cfg.GOOGLE_SPEECH_MODEL || "chirp_3";
  el.googleSpeechLanguageCodes.value = cfg.GOOGLE_SPEECH_LANGUAGE_CODES || "en-US";
  el.googleSpeechChunkSec.value = cfg.GOOGLE_SPEECH_CHUNK_SEC ?? 55;
  el.googleSpeechChunkOverlapSec.value = cfg.GOOGLE_SPEECH_CHUNK_OVERLAP_SEC ?? 0.75;
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
  el.geminiTextTranslateModel.value = cfg.GEMINI_TEXT_TRANSLATE_MODEL || "gemini-2.5-flash";
  el.geminiTextTranslatePrompt.value = cfg.GEMINI_TEXT_TRANSLATE_PROMPT || "";
  el.geminiTtsModel.value = cfg.GEMINI_TTS_MODEL || "gemini-2.5-flash-tts";
  el.geminiTtsVoice.value = cfg.GEMINI_TTS_VOICE || "Kore";
  el.googleTtsProjectId.value = cfg.GOOGLE_TTS_PROJECT_ID || cfg.GOOGLE_SPEECH_PROJECT_ID || "";
  el.googleTtsLanguageCode.value = cfg.GOOGLE_TTS_LANGUAGE_CODE || "en-US";
  el.geminiTtsPrompt.value = cfg.GEMINI_TTS_PROMPT || "";
  el.finalSlideUpscaleMode.value = cfg.FINAL_SLIDE_UPSCALE_MODE || "none";
  el.finalSlideUpscaleModel.value = cfg.FINAL_SLIDE_UPSCALE_MODEL || "caidas/swin2SR-classical-sr-x4-64";
  el.finalSlideUpscaleDevice.value = cfg.FINAL_SLIDE_UPSCALE_DEVICE || "auto";
  el.finalSlideUpscaleTileSize.value = cfg.FINAL_SLIDE_UPSCALE_TILE_SIZE ?? 256;
  el.finalSlideUpscaleTileOverlap.value = cfg.FINAL_SLIDE_UPSCALE_TILE_OVERLAP ?? 24;
  el.replicateNightmareRealesrganModelRef.value = cfg.REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF || "nightmareai/real-esrgan";
  el.replicateNightmareRealesrganVersionId.value = cfg.REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID || "f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa";
  el.replicateNightmareRealesrganPricePerSecond.value = cfg.REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND ?? 0.000225;
  el.replicateUpscaleConcurrency.value = cfg.REPLICATE_UPSCALE_CONCURRENCY ?? 2;
  el.videoExportMinSlideSec.value = cfg.VIDEO_EXPORT_MIN_SLIDE_SEC ?? 1.2;
  el.videoExportTailPadSec.value = cfg.VIDEO_EXPORT_TAIL_PAD_SEC ?? 0.35;
  el.videoExportWidth.value = cfg.VIDEO_EXPORT_WIDTH ?? 1920;
  el.videoExportHeight.value = cfg.VIDEO_EXPORT_HEIGHT ?? 1080;
  el.videoExportFps.value = cfg.VIDEO_EXPORT_FPS ?? 30;
  el.videoExportBgColor.value = cfg.VIDEO_EXPORT_BG_COLOR || "white";
  clearTtsHealthStatus();
  el.labUpscaleProvider.value = ["swin2sr", "replicate_nightmare_realesrgan"].includes(cfg.FINAL_SLIDE_UPSCALE_MODE)
    ? cfg.FINAL_SLIDE_UPSCALE_MODE
    : "swin2sr";
  const videoLabel = cfg.VIDEO_PATH || "(nicht gesetzt)";
  const geminiState = cfg.GEMINI_API_KEY_SET ? "set" : "missing";
  const replicateState = cfg.REPLICATE_API_TOKEN_SET ? "set" : "missing";
  el.configMeta.textContent = `VIDEO_PATH: ${videoLabel} | transcription:${cfg.TRANSCRIPTION_PROVIDER} | source_auto: ${cfg.FINAL_SOURCE_MODE_AUTO} | edit:${cfg.RUN_STEP_EDIT ? "on" : "off"} | image_translate:${cfg.RUN_STEP_TRANSLATE ? "on" : "off"} | upscale:${cfg.RUN_STEP_UPSCALE ? "on" : "off"} | text_translate:${cfg.RUN_STEP_TEXT_TRANSLATE ? "on" : "off"} | tts:${cfg.RUN_STEP_TTS ? "on" : "off"} | video_export:${cfg.RUN_STEP_VIDEO_EXPORT ? "on" : "off"} | final_mode: ${cfg.FINAL_SLIDE_POSTPROCESS_MODE} | image_translate_mode: ${cfg.FINAL_SLIDE_TRANSLATION_MODE} | upscale_mode: ${cfg.FINAL_SLIDE_UPSCALE_MODE} | gemini_key: ${geminiState} | replicate_key: ${replicateState}`;
  syncSettingsFieldState();
  renderSelectedVideo();
}

function setActiveTab(tabName) {
  const allowedTabs = new Set(["home", "all-runs", "image-lab", "roi", "settings"]);
  const nextTab = allowedTabs.has(tabName) ? tabName : "home";
  for (const btn of el.tabButtons) {
    const active = btn.dataset.tab === nextTab;
    btn.classList.toggle("active", active);
  }
  el.panelHome.classList.toggle("active", nextTab === "home");
  el.panelAllRuns.classList.toggle("active", nextTab === "all-runs");
  el.panelImageLab.classList.toggle("active", nextTab === "image-lab");
  el.panelRoi.classList.toggle("active", nextTab === "roi");
  el.panelSettings.classList.toggle("active", nextTab === "settings");
  if (el.saveSettings) {
    el.saveSettings.classList.toggle("hidden", nextTab !== "settings");
  }
  try {
    window.localStorage.setItem(ACTIVE_TAB_STORAGE_KEY, nextTab);
  } catch {
    // Ignore storage failures and keep runtime behavior intact.
  }
}

function getInitialActiveTab() {
  try {
    const stored = window.localStorage.getItem(ACTIVE_TAB_STORAGE_KEY) || "";
    if (["home", "all-runs", "image-lab", "roi", "settings"].includes(stored)) {
      return stored;
    }
  } catch {
    // Ignore storage failures and fall back to home.
  }
  return "home";
}

async function loadConfig() {
  const cfg = await apiGet("/api/config");
  setConfig(cfg);
}

async function saveConfig() {
  const videoPath = (state.selectedVideoPath || "").trim();
  const payload = {
    VIDEO_PATH: videoPath,
    ROI_X0: Number(el.roiX0.value),
    ROI_Y0: Number(el.roiY0.value),
    ROI_X1: Number(el.roiX1.value),
    ROI_Y1: Number(el.roiY1.value),
    RUN_STEP_EDIT: el.runStepEdit.checked ? 1 : 0,
    RUN_STEP_TRANSLATE: el.runStepTranslate.checked ? 1 : 0,
    RUN_STEP_UPSCALE: el.runStepUpscale.checked ? 1 : 0,
    RUN_STEP_TEXT_TRANSLATE: el.runStepTextTranslate.checked ? 1 : 0,
    RUN_STEP_TTS: el.runStepTts.checked ? 1 : 0,
    RUN_STEP_VIDEO_EXPORT: el.runStepVideoExport.checked ? 1 : 0,
    TRANSCRIPTION_PROVIDER: el.transcriptionProvider.value,
    WHISPER_MODEL: el.whisperModel.value.trim(),
    WHISPER_DEVICE: el.whisperDevice.value.trim(),
    WHISPER_COMPUTE_TYPE: el.whisperComputeType.value.trim(),
    WHISPER_LANGUAGE: el.whisperLanguage.value.trim(),
    GOOGLE_SPEECH_PROJECT_ID: el.googleSpeechProjectId.value.trim(),
    GOOGLE_SPEECH_LOCATION: el.googleSpeechLocation.value.trim(),
    GOOGLE_SPEECH_MODEL: el.googleSpeechModel.value.trim(),
    GOOGLE_SPEECH_LANGUAGE_CODES: el.googleSpeechLanguageCodes.value.trim(),
    GOOGLE_SPEECH_CHUNK_SEC: Number(el.googleSpeechChunkSec.value),
    GOOGLE_SPEECH_CHUNK_OVERLAP_SEC: Number(el.googleSpeechChunkOverlapSec.value),
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
    GEMINI_TEXT_TRANSLATE_MODEL: el.geminiTextTranslateModel.value.trim(),
    GEMINI_TEXT_TRANSLATE_PROMPT: el.geminiTextTranslatePrompt.value,
    GEMINI_TTS_MODEL: el.geminiTtsModel.value.trim(),
    GEMINI_TTS_VOICE: el.geminiTtsVoice.value.trim(),
    GOOGLE_TTS_PROJECT_ID: el.googleTtsProjectId.value.trim(),
    GOOGLE_TTS_LANGUAGE_CODE: el.googleTtsLanguageCode.value.trim(),
    GEMINI_TTS_PROMPT: el.geminiTtsPrompt.value,
    FINAL_SLIDE_UPSCALE_MODE: el.finalSlideUpscaleMode.value,
    FINAL_SLIDE_UPSCALE_MODEL: el.finalSlideUpscaleModel.value.trim(),
    FINAL_SLIDE_UPSCALE_DEVICE: el.finalSlideUpscaleDevice.value,
    FINAL_SLIDE_UPSCALE_TILE_SIZE: Number(el.finalSlideUpscaleTileSize.value),
    FINAL_SLIDE_UPSCALE_TILE_OVERLAP: Number(el.finalSlideUpscaleTileOverlap.value),
    REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF: el.replicateNightmareRealesrganModelRef.value.trim(),
    REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID: el.replicateNightmareRealesrganVersionId.value.trim(),
    REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND: Number(el.replicateNightmareRealesrganPricePerSecond.value),
    REPLICATE_UPSCALE_CONCURRENCY: Number(el.replicateUpscaleConcurrency.value),
    VIDEO_EXPORT_MIN_SLIDE_SEC: Number(el.videoExportMinSlideSec.value),
    VIDEO_EXPORT_TAIL_PAD_SEC: Number(el.videoExportTailPadSec.value),
    VIDEO_EXPORT_WIDTH: Number(el.videoExportWidth.value),
    VIDEO_EXPORT_HEIGHT: Number(el.videoExportHeight.value),
    VIDEO_EXPORT_FPS: Number(el.videoExportFps.value),
    VIDEO_EXPORT_BG_COLOR: el.videoExportBgColor.value.trim(),
  };
  await apiPost("/api/config", payload);
  await loadConfig();
}

function showButtonSuccess(button, successLabel, message = "") {
  if (!button) return;
  const existingTimer = buttonFeedbackTimers.get(button);
  if (existingTimer) {
    window.clearTimeout(existingTimer);
  }

  const originalText = button.dataset.originalText || button.textContent;
  button.dataset.originalText = originalText;
  button.textContent = successLabel;
  button.classList.add("is-success");
  if (message) {
    el.configMeta.textContent = message;
  }

  const timer = window.setTimeout(() => {
    button.textContent = button.dataset.originalText || originalText;
    button.classList.remove("is-success");
    buttonFeedbackTimers.delete(button);
  }, 1600);
  buttonFeedbackTimers.set(button, timer);
}

function setTtsHealthStatus(kind, text, meta = "") {
  if (el.ttsHealthStatus) {
    el.ttsHealthStatus.className = `health-check-status is-${kind}`;
    el.ttsHealthStatus.textContent = text;
  }
  if (el.ttsHealthMeta) {
    el.ttsHealthMeta.textContent = meta;
  }
}

function clearTtsHealthStatus() {
  setTtsHealthStatus("idle", "Not tested.", "");
}

function normalizeLanguageLabel(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function expectedTtsLanguagePrefixes(targetLanguage) {
  const normalized = normalizeLanguageLabel(targetLanguage);
  if (!normalized) return [];
  for (const rule of TARGET_LANGUAGE_PREFIX_RULES) {
    if (rule.names.some((name) => normalized.includes(normalizeLanguageLabel(name)))) {
      return rule.prefixes;
    }
  }
  return [];
}

function ttsLanguagePrefix(languageCode) {
  return String(languageCode || "").trim().toLowerCase().split(/[-_]/)[0] || "";
}

function setTtsLanguageHint(kind, text = "") {
  if (!el.ttsLanguageHint) return;
  el.ttsLanguageHint.className = `tts-language-hint muted is-${kind}`;
  el.ttsLanguageHint.textContent = text;
}

function updateTtsLanguageHint() {
  if (!el.ttsLanguageHint) return;
  if (!el.runStepTts.checked) {
    setTtsLanguageHint("idle", "");
    return;
  }
  if (!el.runStepTextTranslate.checked) {
    setTtsLanguageHint("note", "TTS currently speaks the source mapped text because Text Translate is disabled.");
    return;
  }
  const targetLanguage = el.finalSlideTargetLanguage.value.trim();
  const languageCode = el.googleTtsLanguageCode.value.trim();
  if (!targetLanguage || !languageCode) {
    setTtsLanguageHint("idle", "");
    return;
  }
  const expectedPrefixes = expectedTtsLanguagePrefixes(targetLanguage);
  if (expectedPrefixes.length === 0) {
    setTtsLanguageHint("note", `Target language "${targetLanguage}" is free-form. Verify GOOGLE_TTS_LANGUAGE_CODE manually.`);
    return;
  }
  const actualPrefix = ttsLanguagePrefix(languageCode);
  if (!expectedPrefixes.includes(actualPrefix)) {
    setTtsLanguageHint(
      "warning",
      `Target language "${targetLanguage}" usually expects GOOGLE_TTS_LANGUAGE_CODE starting with "${expectedPrefixes[0]}-". Current value: "${languageCode}".`,
    );
    return;
  }
  setTtsLanguageHint("ok", `TTS language code matches the configured target language "${targetLanguage}".`);
}

function collectTtsHealthPayload() {
  return {
    GOOGLE_TTS_PROJECT_ID: el.googleTtsProjectId.value.trim(),
    GOOGLE_TTS_LANGUAGE_CODE: el.googleTtsLanguageCode.value.trim(),
    GEMINI_TTS_MODEL: el.geminiTtsModel.value.trim(),
    GEMINI_TTS_VOICE: el.geminiTtsVoice.value.trim(),
    GEMINI_TTS_PROMPT: el.geminiTtsPrompt.value,
  };
}

async function testTtsHealth() {
  setTtsHealthStatus("pending", "Testing...", "");
  const result = await apiPost("/api/tts/health", collectTtsHealthPayload());
  if (result.ok) {
    const meta = [
      `project=${result.project_id_used || "-"}`,
      `voice=${result.voice || "-"}`,
      `model=${result.model || "-"}`,
      `${result.latency_ms || 0} ms`,
      `${result.audio_bytes || 0} bytes`,
      `${result.duration_sec || 0}s`,
    ].join(" | ");
    setTtsHealthStatus("ok", "Reachable", meta);
    showButtonSuccess(el.ttsHealthCheck, "OK");
    return;
  }
  const meta = [
    result.error_type || "Error",
    result.error_message || result.message || "TTS API check failed.",
  ].filter(Boolean).join(" | ");
  setTtsHealthStatus("error", "Failed", meta);
}

function syncSettingsFieldState() {
  const editEnabled = el.runStepEdit.checked;
  const translateEnabled = el.runStepTranslate.checked;
  const upscaleEnabled = el.runStepUpscale.checked;
  const textTranslateEnabled = el.runStepTextTranslate.checked;
  const ttsEnabled = el.runStepTts.checked;
  const videoExportEnabled = el.runStepVideoExport.checked;
  const transcriptionProvider = el.transcriptionProvider.value;
  const upscaleMode = el.finalSlideUpscaleMode.value;
  const localUpscale = upscaleMode === "swin2sr";
  const replicateUpscale = upscaleMode === "replicate_nightmare_realesrgan";
  const replicateNightmareUpscale = upscaleMode === "replicate_nightmare_realesrgan";
  const googleTranscription = transcriptionProvider === "google_chirp_3";

  el.whisperModel.disabled = googleTranscription;
  el.whisperDevice.disabled = googleTranscription;
  el.whisperComputeType.disabled = googleTranscription;
  el.whisperLanguage.disabled = googleTranscription;
  el.googleSpeechProjectId.disabled = !googleTranscription;
  el.googleSpeechLocation.disabled = !googleTranscription;
  el.googleSpeechModel.disabled = !googleTranscription;
  el.googleSpeechLanguageCodes.disabled = !googleTranscription;
  el.googleSpeechChunkSec.disabled = !googleTranscription;
  el.googleSpeechChunkOverlapSec.disabled = !googleTranscription;

  el.finalSlidePostprocessMode.disabled = !editEnabled;
  el.geminiEditModel.disabled = !editEnabled;
  el.geminiEditPrompt.disabled = !editEnabled;

  el.finalSlideTranslationMode.disabled = !translateEnabled;
  el.finalSlideTargetLanguage.disabled = !(translateEnabled || textTranslateEnabled || ttsEnabled);
  el.geminiTranslateModel.disabled = !translateEnabled;
  el.geminiTranslatePrompt.disabled = !translateEnabled;

  el.geminiTextTranslateModel.disabled = !textTranslateEnabled;
  el.geminiTextTranslatePrompt.disabled = !textTranslateEnabled;

  el.geminiTtsModel.disabled = !ttsEnabled;
  el.geminiTtsVoice.disabled = !ttsEnabled;
  el.googleTtsProjectId.disabled = !ttsEnabled;
  el.googleTtsLanguageCode.disabled = !ttsEnabled;
  el.geminiTtsPrompt.disabled = !ttsEnabled;
  if (el.ttsHealthCheck) {
    el.ttsHealthCheck.disabled = !ttsEnabled;
  }
  if (!ttsEnabled) {
    clearTtsHealthStatus();
  }
  updateTtsLanguageHint();

  el.finalSlideUpscaleMode.disabled = !upscaleEnabled;
  el.finalSlideUpscaleModel.disabled = !upscaleEnabled || !localUpscale;
  el.finalSlideUpscaleDevice.disabled = !upscaleEnabled || !localUpscale;
  el.finalSlideUpscaleTileSize.disabled = !upscaleEnabled || !localUpscale;
  el.finalSlideUpscaleTileOverlap.disabled = !upscaleEnabled || !localUpscale;
  el.replicateNightmareRealesrganModelRef.disabled = !upscaleEnabled || !replicateNightmareUpscale;
  el.replicateNightmareRealesrganVersionId.disabled = !upscaleEnabled || !replicateNightmareUpscale;
  el.replicateNightmareRealesrganPricePerSecond.disabled = !upscaleEnabled || !replicateNightmareUpscale;
  el.replicateUpscaleConcurrency.disabled = !upscaleEnabled || !replicateUpscale;

  el.videoExportMinSlideSec.disabled = !videoExportEnabled;
  el.videoExportTailPadSec.disabled = !videoExportEnabled;
  el.videoExportWidth.disabled = !videoExportEnabled;
  el.videoExportHeight.disabled = !videoExportEnabled;
  el.videoExportFps.disabled = !videoExportEnabled;
  el.videoExportBgColor.disabled = !videoExportEnabled;
  syncStepSections();
}

function closeVideoPicker() {
  el.videoPickerModal.classList.remove("open");
  el.videoPickerModal.setAttribute("aria-hidden", "true");
}

function closeLabImagePicker() {
  el.labImagePickerModal.classList.remove("open");
  el.labImagePickerModal.setAttribute("aria-hidden", "true");
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
      showButtonSuccess(el.pickVideo, "Selected");
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

function syncLabActionState() {
  const hasImage = Boolean(state.labSelectedImage && state.labSelectedImage.image_url);
  const isBusy = state.labStatus === "running";
  el.labPickImage.disabled = isBusy;
  el.labRunEdit.disabled = isBusy || !hasImage;
  el.labRunTranslate.disabled = isBusy || !hasImage;
  el.labRunUpscale.disabled = isBusy || !hasImage;
}

function renderLabSelection() {
  const item = state.labSelectedImage;
  if (!item) {
    el.labSelectedImage.textContent = "Kein Bild gewählt.";
    el.labOriginalImage.removeAttribute("src");
    el.labOriginalImage.onclick = null;
    syncLabActionState();
    return;
  }
  const metaText = `run=${item.run_id} | event=${item.event_id} | ${Number(item.slide_start || 0).toFixed(2)}s - ${Number(item.slide_end || 0).toFixed(2)}s | ${item.name}`;
  el.labSelectedImage.textContent = metaText;
  el.labOriginalImage.src = `${item.image_url}?v=${Date.now()}`;
  el.labOriginalImage.onclick = () => openImageModal(item.image_url, item.name || `event_${item.event_id}`);
  syncLabActionState();
}

function renderLabImagePickerList() {
  const items = state.labImages || [];
  el.labImagePickerList.innerHTML = "";
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "Keine final_slide_images im neuesten Run gefunden.";
    el.labImagePickerList.appendChild(empty);
    return;
  }
  for (const item of items) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "video-item video-file";
    btn.textContent = `event ${item.event_id} | ${Number(item.slide_start || 0).toFixed(2)}s - ${Number(item.slide_end || 0).toFixed(2)}s | ${item.name}`;
    if (state.labSelectedImage && state.labSelectedImage.run_id === item.run_id && state.labSelectedImage.event_id === item.event_id) {
      btn.classList.add("selected");
    }
    btn.addEventListener("click", () => runTask(async () => {
      state.labSelectedImage = item;
      renderLabSelection();
      closeLabImagePicker();
      showButtonSuccess(el.labPickImage, "Selected");
    }));
    el.labImagePickerList.appendChild(btn);
  }
}

async function openLabImagePicker() {
  const data = await apiGet("/api/lab/images");
  state.labImages = data.items || [];
  if (!state.labSelectedImage && state.labImages.length > 0) {
    state.labSelectedImage = state.labImages[0];
    renderLabSelection();
  }
  renderLabImagePickerList();
  el.labImagePickerModal.classList.add("open");
  el.labImagePickerModal.setAttribute("aria-hidden", "false");
}

function setLabStatus(current) {
  const status = current?.status || "idle";
  state.labStatus = status;
  const action = current?.action ? ` | action=${current.action}` : "";
  const provider = current?.provider ? ` | provider=${current.provider}` : "";
  const jobId = current?.job_id ? ` | job=${current.job_id}` : "";
  el.labJobStatus.textContent = `status: ${status}${action}${provider}${jobId}`;
  const resultMeta = [];
  if (current?.message) resultMeta.push(current.message);
  if (current?.input_name) resultMeta.push(`input=${current.input_name}`);
  if (current?.result_name) resultMeta.push(`result=${current.result_name}`);
  if (current?.estimated_cost_usd) resultMeta.push(`est_cost=${formatUsd(current.estimated_cost_usd)}`);
  el.labJobMeta.textContent = resultMeta.length > 0 ? resultMeta.join(" | ") : "Uses current Settings.";
  const logs = (current?.log_tail || []).slice(-120);
  const nextLog = logs.join("\n");
  if (el.labLog.textContent !== nextLog) {
    el.labLog.textContent = nextLog;
    el.labLog.scrollTop = el.labLog.scrollHeight;
  }
  if (current?.result_url) {
    el.labResultImage.src = `${current.result_url}?v=${Date.now()}`;
    el.labResultImage.onclick = () => openImageModal(current.result_url, current.result_name || "lab-result");
  } else {
    el.labResultImage.removeAttribute("src");
    el.labResultImage.onclick = null;
  }
  if (!state.labSelectedImage && current?.original_url) {
    el.labSelectedImage.textContent = current.input_name
      ? `Letzter Testinput: ${current.input_name}`
      : "Letzter Testinput";
    el.labOriginalImage.src = `${current.original_url}?v=${Date.now()}`;
    el.labOriginalImage.onclick = () => openImageModal(current.original_url, current.input_name || "lab-input");
  }
  syncLabActionState();
}

async function loadLabStatus() {
  const current = await apiGet("/api/lab/status");
  setLabStatus(current);
}

async function runLabAction(action) {
  if (!state.labSelectedImage) {
    throw new Error("Bitte zuerst ein Bild im Image Lab wählen.");
  }
  el.labResultImage.removeAttribute("src");
  el.labResultImage.onclick = null;
  const payload = {
    run_id: state.labSelectedImage.run_id,
    event_id: state.labSelectedImage.event_id,
  };
  if (action === "upscale") {
    payload.provider = el.labUpscaleProvider.value;
  }
  const res = await apiPost(`/api/lab/${action}`, payload);
  setLabStatus(res.current || {});
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
  renderDownloadLinks(el.latestDownloads, null);
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
  renderDownloadLinks(el.runDownloads, null);
  el.csvPreview.textContent = "";
  el.runSlidesList.innerHTML = "";
}

function renderRunSelect(runs) {
  el.runSelect.innerHTML = "";
  for (const run of runs) {
    const opt = document.createElement("option");
    opt.value = run.id;
    opt.textContent = `${run.id} | status ${run.run_status || "-"} | available ${run.highest_available_label || "no output yet"} | upscale ${run.upscale_mode_used || "-"} | cost ${formatUsd(run.upscale_estimated_cost_usd)} | base ${run.event_count} | final ${run.final_event_count} | final_img ${run.final_slide_images} | translated ${run.translated_slide_images || 0} | x4 ${run.upscaled_slide_images || 0} | translated_x4 ${run.translated_upscaled_slide_images || 0} | text_tx ${run.translated_text_events || 0} | tts ${run.tts_segments || 0} | video ${run.exported_video_name ? "yes" : "no"}`;
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
  state.latestRunId = preferredLatestRunId(runs, current);
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
  el.runSummary.textContent = buildRunSummary(detail, "run");
  renderDownloadLinks(el.runDownloads, detail);
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
  el.latestSummary.textContent = buildRunSummary(detail, "latest");
  renderDownloadLinks(el.latestDownloads, detail);
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

function canUseX4ForSource(items, slideSourceMode) {
  if (!Array.isArray(items) || items.length === 0) return false;
  if (slideSourceMode === "raw") return false;
  if (slideSourceMode === "translated") {
    return items.every((item) => Boolean(item.translated_upscaled_slide_image_url));
  }
  return items.every((item) => Boolean(item.processed_upscaled_slide_image_url));
}

function applyResolutionAvailability(selectEl, items, slideSourceMode, stateKey, forceDisable = false) {
  if (!selectEl) return;
  const x4Option = selectEl.querySelector('option[value="x4"]');
  if (!x4Option) return;

  const allowX4 = !forceDisable && canUseX4ForSource(items, slideSourceMode);
  x4Option.disabled = !allowX4;
  if (!allowX4 && stateKey && state[stateKey] === "x4") {
    state[stateKey] = "native";
    selectEl.value = "native";
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

function resolveRenderedFinalImage(item, slideSourceMode, resolutionMode) {
  const wantsRaw = slideSourceMode === "raw";
  const wantsTranslated = slideSourceMode === "translated";
  const wantsX4 = resolutionMode === "x4";

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

  if (item.image_mode === "full") {
    return {
      url: item.full_image_url || item.image_url || "",
      name: item.full_image_name || item.image_name || "",
      slideSourceLabel: wantsTranslated ? "translated" : "processed",
      resolutionLabel: "native",
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
    if (resolutionMode === "native" && item.image_mode === "full" && item.full_image_url) {
      return {
        url: item.full_image_url,
        name: item.full_image_name || item.image_name || "",
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
  if (resolutionMode === "native" && item.image_mode === "full" && item.full_image_url) {
    return {
      url: item.full_image_url,
      name: item.full_image_name || item.image_name || "",
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

async function renderFinalSlides(runId, target, slideSourceMode, resolutionMode, displayMode, resolutionSelect = null, resolutionStateKey = "") {
  if (!runId) {
    target.innerHTML = "";
    applyResolutionAvailability(resolutionSelect, [], slideSourceMode, resolutionStateKey, true);
    return;
  }
  const data = await apiGet(`/api/runs/${encodeURIComponent(runId)}/final-slides`);
  const items = data.items || [];
  applyResolutionAvailability(resolutionSelect, items, slideSourceMode, resolutionStateKey, false);

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
    applyResolutionAvailability(el.latestFinalResolutionMode, [], state.latestFinalSourceMode, "latestFinalResolutionMode", true);
    return;
  }
  if (state.latestSlidesMode === "base") {
    applyResolutionAvailability(el.latestFinalResolutionMode, [], state.latestFinalSourceMode, "latestFinalResolutionMode", true);
    await renderBaseEvents(runId, el.latestSlidesList);
    return;
  }
  await renderFinalSlides(
    runId,
    el.latestSlidesList,
    state.latestFinalSourceMode,
    state.latestFinalResolutionMode,
    state.latestFinalDisplayMode,
    el.latestFinalResolutionMode,
    "latestFinalResolutionMode",
  );
}

async function loadRunSlides() {
  const runId = el.runSelect.value;
  if (!runId) {
    el.runSlidesList.innerHTML = "";
    applyResolutionAvailability(el.runFinalResolutionMode, [], state.runFinalSourceMode, "runFinalResolutionMode", true);
    return;
  }
  await renderFinalSlides(
    runId,
    el.runSlidesList,
    state.runFinalSourceMode,
    state.runFinalResolutionMode,
    state.runFinalDisplayMode,
    el.runFinalResolutionMode,
    "runFinalResolutionMode",
  );
}

async function startRun() {
  await apiPost("/api/runs", {});
  await loadRuns();
}

async function stopRun() {
  await apiPost("/api/runs/stop", {});
  const current = await apiGet("/api/runs/current");
  setStatus(current);
}

async function pollCurrent() {
  try {
    const current = await apiGet("/api/runs/current");
    setStatus(current);
    if (current.run_id && current.status && current.status !== "idle") {
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

function bindEvents() {
  for (const btn of el.tabButtons) {
    btn.addEventListener("click", () => setActiveTab(btn.dataset.tab));
  }
  el.saveRoi.addEventListener("click", () => runTask(async () => {
    await saveConfig();
    showButtonSuccess(el.saveRoi, "Saved", "ROI settings saved.");
  }));
  el.saveSettings.addEventListener("click", () => runTask(async () => {
    await saveConfig();
    showButtonSuccess(el.saveSettings, "Saved", "Settings saved.");
  }));
  el.ttsHealthCheck.addEventListener("click", () => runTask(async () => {
    await testTtsHealth();
  }));
  el.regenOverlay.addEventListener("click", () => runTask(async () => {
    await regenerateOverlay();
    showButtonSuccess(el.regenOverlay, "Generated");
  }));
  el.refreshOverlay.addEventListener("click", () => runTask(async () => {
    await loadOverlay();
    showButtonSuccess(el.refreshOverlay, "Refreshed");
  }));
  el.startRun.addEventListener("click", () => runTask(async () => {
    await startRun();
    showButtonSuccess(el.startRun, "Started");
  }));
  el.openStatus.addEventListener("click", openStatusModal);
  el.stopRun.addEventListener("click", () => runTask(async () => {
    await stopRun();
  }));
  el.refreshRuns.addEventListener("click", () => runTaskImmediate(async () => {
    await loadRuns();
    showButtonSuccess(el.refreshRuns, "Refreshed");
  }));
  el.pickVideo.addEventListener("click", () => runTask(openVideoPicker));
  el.labPickImage.addEventListener("click", () => runTask(openLabImagePicker));
  el.labRunEdit.addEventListener("click", () => runTask(async () => {
    await runLabAction("edit");
    showButtonSuccess(el.labRunEdit, "Started");
  }));
  el.labRunTranslate.addEventListener("click", () => runTask(async () => {
    await runLabAction("translate");
    showButtonSuccess(el.labRunTranslate, "Started");
  }));
  el.labRunUpscale.addEventListener("click", () => runTask(async () => {
    await runLabAction("upscale");
    showButtonSuccess(el.labRunUpscale, "Started");
  }));
  el.transcriptionProvider.addEventListener("change", syncSettingsFieldState);
  el.finalSlideUpscaleMode.addEventListener("change", syncSettingsFieldState);

  for (const input of [
    el.runStepEdit,
    el.runStepTranslate,
    el.runStepUpscale,
    el.runStepTextTranslate,
    el.runStepTts,
    el.runStepVideoExport,
  ]) {
    input.addEventListener("change", () => {
      syncSettingsFieldState();
    });
  }

  for (const input of [
    el.googleTtsProjectId,
    el.googleTtsLanguageCode,
    el.geminiTtsModel,
    el.geminiTtsVoice,
    el.geminiTtsPrompt,
  ]) {
    input.addEventListener("input", clearTtsHealthStatus);
    input.addEventListener("change", clearTtsHealthStatus);
  }

  for (const input of [
    el.finalSlideTargetLanguage,
    el.googleTtsLanguageCode,
    el.runStepTts,
    el.runStepTextTranslate,
  ]) {
    input.addEventListener("input", updateTtsLanguageHint);
    input.addEventListener("change", updateTtsLanguageHint);
  }

  document.querySelectorAll(".step-section-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const sectionId = button.dataset.stepToggle;
      if (!sectionId || button.disabled) return;
      state.stepSectionExpanded[sectionId] = !state.stepSectionExpanded[sectionId];
      syncStepSections();
    });
  });
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
  el.statusModalClose.addEventListener("click", closeStatusModal);
  el.statusModalBackdrop.addEventListener("click", closeStatusModal);
  el.labImagePickerClose.addEventListener("click", closeLabImagePicker);
  el.labImagePickerBackdrop.addEventListener("click", closeLabImagePicker);
  el.videoPickerClose.addEventListener("click", closeVideoPicker);
  el.videoPickerBackdrop.addEventListener("click", closeVideoPicker);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && el.imageModal.classList.contains("open")) {
      closeImageModal();
    }
    if (e.key === "Escape" && el.statusModal.classList.contains("open")) {
      closeStatusModal();
    }
    if (e.key === "Escape" && el.labImagePickerModal.classList.contains("open")) {
      closeLabImagePicker();
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
  syncSettingsFieldState();
  syncLabActionState();
  setActiveTab(getInitialActiveTab());
  await runTask(loadConfig);
  await runTask(loadOverlay);
  await runTask(loadRuns);
  await runTask(loadLabStatus);
  setInterval(pollCurrent, 2000);
  setInterval(() => { runTaskImmediate(loadLabStatus); }, 2000);
}

init();
