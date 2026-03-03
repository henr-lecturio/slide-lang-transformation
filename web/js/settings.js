import { el } from "./dom.js";
import { state } from "./state.js";
import { apiGet, apiPost } from "./api.js";
import { videoThumbUrl } from "./ui-core.js";
import { clearHealthStatus, setHealthStatus } from "./health-checks.js";
import { getSelectedTtsLanguageOption, renderTtsLanguageOptions, updateTtsLanguageHint } from "./tts-language.js";

function isStepSectionEnabled(section) {
  const inputId = section?.dataset?.stepInput || "";
  if (!inputId) return true;
  const input = document.getElementById(inputId);
  return Boolean(input && input.checked);
}

export function syncStepSections() {
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

export function renderSelectedVideo(syncActionState = () => {}) {
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

export function setConfig(cfg, { syncActionState = () => {} } = {}) {
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
  state.ttsLanguageOptions = Array.isArray(cfg.GEMINI_TTS_LANGUAGE_OPTIONS) ? cfg.GEMINI_TTS_LANGUAGE_OPTIONS : [];
  if (el.finalSlideTargetLanguageSearch) {
    el.finalSlideTargetLanguageSearch.value = "";
  }
  renderTtsLanguageOptions("", cfg.GOOGLE_TTS_LANGUAGE_CODE || "", cfg.FINAL_SLIDE_TARGET_LANGUAGE || "");
  el.geminiTranslateModel.value = cfg.GEMINI_TRANSLATE_MODEL || "gemini-3-pro-image-preview";
  el.geminiTranslatePrompt.value = cfg.GEMINI_TRANSLATE_PROMPT || "";
  el.geminiTextTranslateModel.value = cfg.GEMINI_TEXT_TRANSLATE_MODEL || "gemini-2.5-flash";
  el.geminiTextTranslatePrompt.value = cfg.GEMINI_TEXT_TRANSLATE_PROMPT || "";
  el.geminiTtsModel.value = cfg.GEMINI_TTS_MODEL || "gemini-2.5-flash-tts";
  el.geminiTtsVoice.value = cfg.GEMINI_TTS_VOICE || "Kore";
  el.googleTtsProjectId.value = cfg.GOOGLE_TTS_PROJECT_ID || cfg.GOOGLE_SPEECH_PROJECT_ID || "";
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
  clearHealthStatus("transcription");
  clearHealthStatus("slideEdit");
  clearHealthStatus("slideTranslate");
  clearHealthStatus("slideUpscale");
  clearHealthStatus("textTranslate");
  clearHealthStatus("tts");
  const videoLabel = cfg.VIDEO_PATH || "(nicht gesetzt)";
  el.configMeta.textContent = `VIDEO_PATH: ${videoLabel}`;
  syncSettingsFieldState();
  renderSelectedVideo(syncActionState);
}


export async function loadConfig(options = {}) {
  const cfg = await apiGet("/api/config");
  setConfig(cfg, options);
  return cfg;
}

export async function saveConfig(options = {}) {
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
    FINAL_SLIDE_TARGET_LANGUAGE: (getSelectedTtsLanguageOption()?.label || "").trim(),
    GEMINI_TRANSLATE_MODEL: el.geminiTranslateModel.value.trim(),
    GEMINI_TRANSLATE_PROMPT: el.geminiTranslatePrompt.value,
    GEMINI_TEXT_TRANSLATE_MODEL: el.geminiTextTranslateModel.value.trim(),
    GEMINI_TEXT_TRANSLATE_PROMPT: el.geminiTextTranslatePrompt.value,
    GEMINI_TTS_MODEL: el.geminiTtsModel.value.trim(),
    GEMINI_TTS_VOICE: el.geminiTtsVoice.value.trim(),
    GOOGLE_TTS_PROJECT_ID: el.googleTtsProjectId.value.trim(),
    GOOGLE_TTS_LANGUAGE_CODE: (getSelectedTtsLanguageOption()?.tts_language_code || "").trim(),
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
  return await loadConfig(options);
}


export function syncSettingsFieldState() {
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
  const slideUpscaleApiEnabled = upscaleEnabled && upscaleMode !== "none";
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
  if (el.transcriptionHealthCheck) {
    el.transcriptionHealthCheck.disabled = !googleTranscription;
  }
  if (!googleTranscription) {
    setHealthStatus("transcription", "idle", "Only for google_chirp_3.", "");
  } else if (el.transcriptionHealthStatus?.textContent === "Only for google_chirp_3.") {
    clearHealthStatus("transcription");
  }

  el.finalSlidePostprocessMode.disabled = !editEnabled;
  el.geminiEditModel.disabled = !editEnabled;
  el.geminiEditPrompt.disabled = !editEnabled;
  const editApiEnabled = editEnabled && el.finalSlidePostprocessMode.value === "gemini";
  if (el.slideEditHealthCheck) {
    el.slideEditHealthCheck.disabled = !editApiEnabled;
  }
  if (!editApiEnabled) {
    setHealthStatus("slideEdit", "idle", editEnabled ? "Only for gemini mode." : "Step disabled.", "");
  } else if (
    el.slideEditHealthStatus?.textContent === "Only for gemini mode."
    || el.slideEditHealthStatus?.textContent === "Step disabled."
  ) {
    clearHealthStatus("slideEdit");
  }

  el.finalSlideTranslationMode.disabled = !translateEnabled;
  const languageSelectionEnabled = translateEnabled || textTranslateEnabled || ttsEnabled;
  if (el.finalSlideTargetLanguageSearch) {
    el.finalSlideTargetLanguageSearch.disabled = !languageSelectionEnabled;
  }
  el.finalSlideTargetLanguage.disabled = !languageSelectionEnabled;
  el.geminiTranslateModel.disabled = !translateEnabled;
  el.geminiTranslatePrompt.disabled = !translateEnabled;
  const slideTranslateApiEnabled = translateEnabled && el.finalSlideTranslationMode.value === "gemini";
  if (el.slideTranslateHealthCheck) {
    el.slideTranslateHealthCheck.disabled = !slideTranslateApiEnabled;
  }
  if (!slideTranslateApiEnabled) {
    setHealthStatus("slideTranslate", "idle", translateEnabled ? "Only for gemini mode." : "Step disabled.", "");
  } else if (
    el.slideTranslateHealthStatus?.textContent === "Only for gemini mode."
    || el.slideTranslateHealthStatus?.textContent === "Step disabled."
  ) {
    clearHealthStatus("slideTranslate");
  }

  el.geminiTextTranslateModel.disabled = !textTranslateEnabled;
  el.geminiTextTranslatePrompt.disabled = !textTranslateEnabled;
  if (el.textTranslateHealthCheck) {
    el.textTranslateHealthCheck.disabled = !textTranslateEnabled;
  }
  if (!textTranslateEnabled) {
    setHealthStatus("textTranslate", "idle", "Step disabled.", "");
  } else if (el.textTranslateHealthStatus?.textContent === "Step disabled.") {
    clearHealthStatus("textTranslate");
  }

  el.geminiTtsModel.disabled = !ttsEnabled;
  el.geminiTtsVoice.disabled = !ttsEnabled;
  el.googleTtsProjectId.disabled = !ttsEnabled;
  el.googleTtsLanguageCode.disabled = !ttsEnabled;
  el.geminiTtsPrompt.disabled = !ttsEnabled;
  if (el.ttsHealthCheck) {
    el.ttsHealthCheck.disabled = !ttsEnabled;
  }
  if (!ttsEnabled) {
    setHealthStatus("tts", "idle", "Step disabled.", "");
  } else if (el.ttsHealthStatus?.textContent === "Step disabled.") {
    clearHealthStatus("tts");
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
  if (el.slideUpscaleHealthCheck) {
    el.slideUpscaleHealthCheck.disabled = !slideUpscaleApiEnabled;
  }
  if (!slideUpscaleApiEnabled) {
    setHealthStatus("slideUpscale", "idle", upscaleEnabled ? "Select an upscale mode." : "Step disabled.", "");
  } else if (
    el.slideUpscaleHealthStatus?.textContent === "Select an upscale mode."
    || el.slideUpscaleHealthStatus?.textContent === "Step disabled."
  ) {
    clearHealthStatus("slideUpscale");
  }

  el.videoExportMinSlideSec.disabled = !videoExportEnabled;
  el.videoExportTailPadSec.disabled = !videoExportEnabled;
  el.videoExportWidth.disabled = !videoExportEnabled;
  el.videoExportHeight.disabled = !videoExportEnabled;
  el.videoExportFps.disabled = !videoExportEnabled;
  el.videoExportBgColor.disabled = !videoExportEnabled;
  syncStepSections();
}
