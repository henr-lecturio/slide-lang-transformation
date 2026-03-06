import { el } from "./dom.js";
import { apiPost } from "./api.js";
import { formatUsd, showButtonSuccess } from "./ui-core.js";
import { getSelectedTtsLanguageOption } from "./tts-language.js";

const healthUi = {
  gemini: {
    button: () => el.geminiHealthCheck,
    status: () => el.geminiHealthStatus,
    toggle: () => el.geminiHealthMetaToggle,
    wrap: () => el.geminiHealthMetaWrap,
    meta: () => el.geminiHealthMeta,
  },
  speechToText: {
    button: () => el.speechToTextHealthCheck,
    status: () => el.speechToTextHealthStatus,
    toggle: () => el.speechToTextHealthMetaToggle,
    wrap: () => el.speechToTextHealthMetaWrap,
    meta: () => el.speechToTextHealthMeta,
  },
  cloudTranslation: {
    button: () => el.cloudTranslationHealthCheck,
    status: () => el.cloudTranslationHealthStatus,
    toggle: () => el.cloudTranslationHealthMetaToggle,
    wrap: () => el.cloudTranslationHealthMetaWrap,
    meta: () => el.cloudTranslationHealthMeta,
  },
  cloudVision: {
    button: () => el.cloudVisionHealthCheck,
    status: () => el.cloudVisionHealthStatus,
    toggle: () => el.cloudVisionHealthMetaToggle,
    wrap: () => el.cloudVisionHealthMetaWrap,
    meta: () => el.cloudVisionHealthMeta,
  },
  cloudTts: {
    button: () => el.cloudTtsHealthCheck,
    status: () => el.cloudTtsHealthStatus,
    toggle: () => el.cloudTtsHealthMetaToggle,
    wrap: () => el.cloudTtsHealthMetaWrap,
    meta: () => el.cloudTtsHealthMeta,
  },
  replicate: {
    button: () => el.replicateHealthCheck,
    status: () => el.replicateHealthStatus,
    toggle: () => el.replicateHealthMetaToggle,
    wrap: () => el.replicateHealthMetaWrap,
    meta: () => el.replicateHealthMeta,
  },
};

function setMetaOpen(ui, open) {
  const toggleEl = ui.toggle?.();
  const wrapEl = ui.wrap?.();
  if (toggleEl) {
    toggleEl.setAttribute("aria-expanded", open ? "true" : "false");
  }
  if (wrapEl) {
    wrapEl.hidden = !open;
    wrapEl.classList.toggle("is-open", open);
  }
}

export function toggleHealthMeta(key) {
  const ui = healthUi[key];
  if (!ui) return;
  const toggleEl = ui.toggle?.();
  const wrapEl = ui.wrap?.();
  if (!toggleEl || !wrapEl || toggleEl.disabled) return;
  const nextOpen = toggleEl.getAttribute("aria-expanded") !== "true";
  setMetaOpen(ui, nextOpen);
}

export function setHealthStatus(key, kind, text, meta = "") {
  const ui = healthUi[key];
  if (!ui) return;
  const statusEl = ui.status();
  const toggleEl = ui.toggle?.();
  const wrapEl = ui.wrap?.();
  const metaEl = ui.meta();
  if (statusEl) {
    statusEl.className = `health-check-status is-${kind}`;
    statusEl.textContent = text;
  }
  if (metaEl) {
    metaEl.textContent = meta;
  }
  const hasMeta = Boolean(String(meta || "").trim());
  if (toggleEl) {
    toggleEl.disabled = !hasMeta;
  }
  if (!hasMeta && wrapEl) {
    setMetaOpen(ui, false);
  }
}

export function clearHealthStatus(key, text = "Not tested.") {
  setHealthStatus(key, "idle", text, "");
}

function projectId() {
  return el.gcloudProjectId.value.trim();
}

function collectGeminiHealthPayload() {
  return {
    GCLOUD_PROJECT_ID: projectId(),
    GEMINI_EDIT_MODEL: el.geminiEditModel.value.trim(),
  };
}

function collectSpeechToTextHealthPayload() {
  return {
    GCLOUD_PROJECT_ID: projectId(),
    TRANSCRIPTION_PROVIDER: el.transcriptionProvider.value,
    GOOGLE_SPEECH_LOCATION: el.googleSpeechLocation.value.trim(),
    GOOGLE_SPEECH_MODEL: el.googleSpeechModel.value.trim(),
    GOOGLE_SPEECH_LANGUAGE_CODES: el.googleSpeechLanguageCodes.value.trim(),
  };
}

function collectCloudTranslationHealthPayload() {
  return {
    GCLOUD_PROJECT_ID: projectId(),
    GOOGLE_TRANSLATE_LOCATION: el.googleTranslateLocation.value.trim(),
    GOOGLE_TRANSLATE_SOURCE_LANGUAGE_CODE: el.googleTranslateSourceLanguageCode.value.trim(),
    FINAL_SLIDE_TARGET_LANGUAGE: (getSelectedTtsLanguageOption()?.label || "").trim(),
  };
}

function collectCloudVisionHealthPayload() {
  return {
    GCLOUD_PROJECT_ID: projectId(),
  };
}

function collectCloudTtsHealthPayload() {
  const selected = getSelectedTtsLanguageOption();
  return {
    GCLOUD_PROJECT_ID: projectId(),
    GOOGLE_TTS_LANGUAGE_CODE: selected ? selected.tts_language_code : "",
    GEMINI_TTS_MODEL: el.geminiTtsModel.value.trim(),
    GEMINI_TTS_VOICE: el.geminiTtsVoice.value.trim(),
    GEMINI_TTS_PROMPT: el.geminiTtsPrompt.value,
  };
}

function collectReplicateHealthPayload() {
  return {
    REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF: el.replicateNightmareRealesrganModelRef.value.trim(),
    REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID: el.replicateNightmareRealesrganVersionId.value.trim(),
    REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND: Number(el.replicateNightmareRealesrganPricePerSecond.value),
  };
}

export async function testGeminiHealth() {
  setHealthStatus("gemini", "pending", "Testing...", "");
  const result = await apiPost("/api/gemini/health", collectGeminiHealthPayload());
  if (result.ok) {
    const meta = [
      `model=${result.model || "-"}`,
      `project=${result.project_id_used || "-"}`,
      `location=${result.location || "-"}`,
      `${result.latency_ms || 0} ms`,
      `${result.image_width || 0}x${result.image_height || 0}`,
      `${result.image_bytes || 0} bytes`,
    ].join(" | ");
    setHealthStatus("gemini", "ok", "Reachable", meta);
    showButtonSuccess(el.geminiHealthCheck, "OK");
    return;
  }
  const meta = [result.error_type || "Error", result.error_message || result.message || "Gemini API check failed."]
    .filter(Boolean)
    .join(" | ");
  setHealthStatus("gemini", "error", "Failed", meta);
}

export async function testSpeechToTextHealth() {
  setHealthStatus("speechToText", "pending", "Testing...", "");
  const result = await apiPost("/api/transcription/health", collectSpeechToTextHealthPayload());
  if (result.ok) {
    const meta = [
      `project=${result.project_id || "-"}`,
      `location=${result.location || "-"}`,
      `model=${result.model || "-"}`,
      `languages=${Array.isArray(result.language_codes) ? result.language_codes.join(",") : "-"}`,
      `${result.latency_ms || 0} ms`,
      `results=${result.results_count || 0}`,
    ].join(" | ");
    setHealthStatus("speechToText", "ok", "Reachable", meta);
    showButtonSuccess(el.speechToTextHealthCheck, "OK");
    return;
  }
  const meta = [result.error_type || "Error", result.error_message || result.message || "Speech-to-Text API check failed."]
    .filter(Boolean)
    .join(" | ");
  setHealthStatus("speechToText", "error", "Failed", meta);
}

export async function testCloudTranslationHealth() {
  setHealthStatus("cloudTranslation", "pending", "Testing...", "");
  const result = await apiPost("/api/cloud-translation/health", collectCloudTranslationHealthPayload());
  if (result.ok) {
    const translated = String(result.translated_text || "").trim();
    const preview = translated.length > 90 ? `${translated.slice(0, 87)}...` : translated;
    const meta = [
      `project=${result.project_id_used || "-"}`,
      `location=${result.location || "-"}`,
      `model=${result.model || "-"}`,
      `target=${result.target_language_code || "-"}`,
      `${result.latency_ms || 0} ms`,
      preview ? `sample="${preview}"` : "",
    ].filter(Boolean).join(" | ");
    setHealthStatus("cloudTranslation", "ok", "Reachable", meta);
    showButtonSuccess(el.cloudTranslationHealthCheck, "OK");
    return;
  }
  const meta = [result.error_type || "Error", result.error_message || result.message || "Cloud Translation API check failed."]
    .filter(Boolean)
    .join(" | ");
  setHealthStatus("cloudTranslation", "error", "Failed", meta);
}

export async function testCloudVisionHealth() {
  setHealthStatus("cloudVision", "pending", "Testing...", "");
  const result = await apiPost("/api/cloud-vision/health", collectCloudVisionHealthPayload());
  if (result.ok) {
    const meta = [
      `project=${result.project_id_used || "-"}`,
      `${result.latency_ms || 0} ms`,
      result.ocr_preview ? `ocr="${result.ocr_preview}"` : "",
    ].filter(Boolean).join(" | ");
    setHealthStatus("cloudVision", "ok", "Reachable", meta);
    showButtonSuccess(el.cloudVisionHealthCheck, "OK");
    return;
  }
  const meta = [result.error_type || "Error", result.error_message || result.message || "Cloud Vision API check failed."]
    .filter(Boolean)
    .join(" | ");
  setHealthStatus("cloudVision", "error", "Failed", meta);
}

export async function testCloudTtsHealth() {
  setHealthStatus("cloudTts", "pending", "Testing...", "");
  const result = await apiPost("/api/tts/health", collectCloudTtsHealthPayload());
  if (result.ok) {
    const meta = [
      `project=${result.project_id_used || "-"}`,
      `voice=${result.voice || "-"}`,
      `model=${result.model || "-"}`,
      `${result.latency_ms || 0} ms`,
      `${result.audio_bytes || 0} bytes`,
      `${result.duration_sec || 0}s`,
    ].join(" | ");
    setHealthStatus("cloudTts", "ok", "Reachable", meta);
    showButtonSuccess(el.cloudTtsHealthCheck, "OK");
    return;
  }
  const meta = [
    result.error_type || "Error",
    result.error_message || result.message || "Cloud TTS API check failed.",
  ].filter(Boolean).join(" | ");
  setHealthStatus("cloudTts", "error", "Failed", meta);
}

export async function testReplicateHealth() {
  setHealthStatus("replicate", "pending", "Testing...", "");
  const result = await apiPost("/api/replicate/health", collectReplicateHealthPayload());
  if (result.ok) {
    const metaParts = [
      `model=${result.model || "-"}`,
      result.version_id ? `version=${result.version_id}` : "",
      `x${result.scale || 4}`,
      `${result.latency_ms || 0} ms`,
      `${result.image_width || 0}x${result.image_height || 0}`,
      result.predict_time_sec != null ? `predict=${Number(result.predict_time_sec).toFixed(3)}s` : "",
      result.estimated_cost_usd != null && result.estimated_cost_usd > 0 ? `est_cost=${formatUsd(result.estimated_cost_usd)}` : "",
    ].filter(Boolean);
    setHealthStatus("replicate", "ok", "Reachable", metaParts.join(" | "));
    showButtonSuccess(el.replicateHealthCheck, "OK");
    return;
  }
  const meta = [result.error_type || "Error", result.error_message || result.message || "Replicate API check failed."]
    .filter(Boolean)
    .join(" | ");
  setHealthStatus("replicate", "error", "Failed", meta);
}
