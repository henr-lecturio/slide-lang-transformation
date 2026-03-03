import { el } from "./dom.js";
import { apiPost } from "./api.js";
import { formatUsd, showButtonSuccess } from "./ui-core.js";
import { getSelectedTtsLanguageOption } from "./tts-language.js";

const healthUi = {
  transcription: {
    button: () => el.transcriptionHealthCheck,
    status: () => el.transcriptionHealthStatus,
    meta: () => el.transcriptionHealthMeta,
  },
  slideEdit: {
    button: () => el.slideEditHealthCheck,
    status: () => el.slideEditHealthStatus,
    meta: () => el.slideEditHealthMeta,
  },
  slideTranslate: {
    button: () => el.slideTranslateHealthCheck,
    status: () => el.slideTranslateHealthStatus,
    meta: () => el.slideTranslateHealthMeta,
  },
  textTranslate: {
    button: () => el.textTranslateHealthCheck,
    status: () => el.textTranslateHealthStatus,
    meta: () => el.textTranslateHealthMeta,
  },
  slideUpscale: {
    button: () => el.slideUpscaleHealthCheck,
    status: () => el.slideUpscaleHealthStatus,
    meta: () => el.slideUpscaleHealthMeta,
  },
  tts: {
    button: () => el.ttsHealthCheck,
    status: () => el.ttsHealthStatus,
    meta: () => el.ttsHealthMeta,
  },
};

export function setHealthStatus(key, kind, text, meta = "") {
  const ui = healthUi[key];
  if (!ui) return;
  const statusEl = ui.status();
  const metaEl = ui.meta();
  if (statusEl) {
    statusEl.className = `health-check-status is-${kind}`;
    statusEl.textContent = text;
  }
  if (metaEl) {
    metaEl.textContent = meta;
  }
}

export function clearHealthStatus(key, text = "Not tested.") {
  setHealthStatus(key, "idle", text, "");
}

function collectTtsHealthPayload() {
  const selected = getSelectedTtsLanguageOption();
  return {
    GOOGLE_TTS_PROJECT_ID: el.googleTtsProjectId.value.trim(),
    GOOGLE_TTS_LANGUAGE_CODE: selected ? selected.tts_language_code : "",
    GEMINI_TTS_MODEL: el.geminiTtsModel.value.trim(),
    GEMINI_TTS_VOICE: el.geminiTtsVoice.value.trim(),
    GEMINI_TTS_PROMPT: el.geminiTtsPrompt.value,
  };
}

function collectTranscriptionHealthPayload() {
  return {
    TRANSCRIPTION_PROVIDER: el.transcriptionProvider.value,
    GOOGLE_SPEECH_PROJECT_ID: el.googleSpeechProjectId.value.trim(),
    GOOGLE_SPEECH_LOCATION: el.googleSpeechLocation.value.trim(),
    GOOGLE_SPEECH_MODEL: el.googleSpeechModel.value.trim(),
    GOOGLE_SPEECH_LANGUAGE_CODES: el.googleSpeechLanguageCodes.value.trim(),
  };
}

function collectSlideEditHealthPayload() {
  return {
    FINAL_SLIDE_POSTPROCESS_MODE: el.finalSlidePostprocessMode.value,
    GEMINI_EDIT_MODEL: el.geminiEditModel.value.trim(),
    GEMINI_EDIT_PROMPT: el.geminiEditPrompt.value,
  };
}

function collectSlideTranslateHealthPayload() {
  return {
    FINAL_SLIDE_TRANSLATION_MODE: el.finalSlideTranslationMode.value,
    FINAL_SLIDE_TARGET_LANGUAGE: (getSelectedTtsLanguageOption()?.label || "").trim(),
    GEMINI_TRANSLATE_MODEL: el.geminiTranslateModel.value.trim(),
    GEMINI_TRANSLATE_PROMPT: el.geminiTranslatePrompt.value,
  };
}

function collectTextTranslateHealthPayload() {
  return {
    FINAL_SLIDE_TARGET_LANGUAGE: (getSelectedTtsLanguageOption()?.label || "").trim(),
    GEMINI_TEXT_TRANSLATE_MODEL: el.geminiTextTranslateModel.value.trim(),
    GEMINI_TEXT_TRANSLATE_PROMPT: el.geminiTextTranslatePrompt.value,
  };
}

function collectSlideUpscaleHealthPayload() {
  return {
    FINAL_SLIDE_UPSCALE_MODE: el.finalSlideUpscaleMode.value,
    FINAL_SLIDE_UPSCALE_MODEL: el.finalSlideUpscaleModel.value.trim(),
    FINAL_SLIDE_UPSCALE_DEVICE: el.finalSlideUpscaleDevice.value,
    FINAL_SLIDE_UPSCALE_TILE_SIZE: Number(el.finalSlideUpscaleTileSize.value),
    FINAL_SLIDE_UPSCALE_TILE_OVERLAP: Number(el.finalSlideUpscaleTileOverlap.value),
    REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF: el.replicateNightmareRealesrganModelRef.value.trim(),
    REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID: el.replicateNightmareRealesrganVersionId.value.trim(),
    REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND: Number(el.replicateNightmareRealesrganPricePerSecond.value),
  };
}

export async function testTranscriptionHealth() {
  setHealthStatus("transcription", "pending", "Testing...", "");
  const result = await apiPost("/api/transcription/health", collectTranscriptionHealthPayload());
  if (result.ok) {
    const meta = [
      `project=${result.project_id || "-"}`,
      `location=${result.location || "-"}`,
      `model=${result.model || "-"}`,
      `languages=${Array.isArray(result.language_codes) ? result.language_codes.join(",") : "-"}`,
      `${result.latency_ms || 0} ms`,
      `results=${result.results_count || 0}`,
    ].join(" | ");
    setHealthStatus("transcription", "ok", "Reachable", meta);
    showButtonSuccess(el.transcriptionHealthCheck, "OK");
    return;
  }
  const meta = [result.error_type || "Error", result.error_message || result.message || "Transcription API check failed."]
    .filter(Boolean)
    .join(" | ");
  setHealthStatus("transcription", "error", "Failed", meta);
}

export async function testSlideEditHealth() {
  setHealthStatus("slideEdit", "pending", "Testing...", "");
  const result = await apiPost("/api/slide-edit/health", collectSlideEditHealthPayload());
  if (result.ok) {
    const meta = [
      `model=${result.model || "-"}`,
      `${result.latency_ms || 0} ms`,
      `${result.image_width || 0}x${result.image_height || 0}`,
      `${result.image_bytes || 0} bytes`,
    ].join(" | ");
    setHealthStatus("slideEdit", "ok", "Reachable", meta);
    showButtonSuccess(el.slideEditHealthCheck, "OK");
    return;
  }
  const meta = [result.error_type || "Error", result.error_message || result.message || "Slide Edit API check failed."]
    .filter(Boolean)
    .join(" | ");
  setHealthStatus("slideEdit", "error", "Failed", meta);
}

export async function testSlideTranslateHealth() {
  setHealthStatus("slideTranslate", "pending", "Testing...", "");
  const result = await apiPost("/api/slide-translate/health", collectSlideTranslateHealthPayload());
  if (result.ok) {
    const meta = [
      `target=${result.target_language || "-"}`,
      `model=${result.model || "-"}`,
      result.glossary_entries != null ? `glossary=${result.glossary_entries}` : "",
      `${result.latency_ms || 0} ms`,
      `${result.image_width || 0}x${result.image_height || 0}`,
      `${result.image_bytes || 0} bytes`,
    ].join(" | ");
    setHealthStatus("slideTranslate", "ok", "Reachable", meta);
    showButtonSuccess(el.slideTranslateHealthCheck, "OK");
    return;
  }
  const meta = [result.error_type || "Error", result.error_message || result.message || "Slide Translate API check failed."]
    .filter(Boolean)
    .join(" | ");
  setHealthStatus("slideTranslate", "error", "Failed", meta);
}

export async function testTextTranslateHealth() {
  setHealthStatus("textTranslate", "pending", "Testing...", "");
  const result = await apiPost("/api/text-translate/health", collectTextTranslateHealthPayload());
  if (result.ok) {
    const translated = String(result.translated_text || "").trim();
    const preview = translated.length > 90 ? `${translated.slice(0, 87)}...` : translated;
    const meta = [
      `target=${result.target_language || "-"}`,
      `model=${result.model || "-"}`,
      result.glossary_entries != null ? `glossary=${result.glossary_entries}` : "",
      result.termbase_hits != null ? `termbase_hits=${result.termbase_hits}` : "",
      `${result.latency_ms || 0} ms`,
      preview ? `sample=\"${preview}\"` : "",
    ].filter(Boolean).join(" | ");
    setHealthStatus("textTranslate", "ok", "Reachable", meta);
    showButtonSuccess(el.textTranslateHealthCheck, "OK");
    return;
  }
  const meta = [result.error_type || "Error", result.error_message || result.message || "Text Translate API check failed."]
    .filter(Boolean)
    .join(" | ");
  setHealthStatus("textTranslate", "error", "Failed", meta);
}

export async function testSlideUpscaleHealth() {
  setHealthStatus("slideUpscale", "pending", "Testing...", "");
  const result = await apiPost("/api/slide-upscale/health", collectSlideUpscaleHealthPayload());
  if (result.ok) {
    const metaParts = [
      `mode=${result.mode || "-"}`,
      `model=${result.model || "-"}`,
      result.version_id ? `version=${result.version_id}` : "",
      result.device ? `device=${result.device}` : "",
      result.scale ? `x${result.scale}` : "",
      `${result.latency_ms || 0} ms`,
      `${result.image_width || 0}x${result.image_height || 0}`,
      result.predict_time_sec != null ? `predict=${Number(result.predict_time_sec).toFixed(3)}s` : "",
      result.estimated_cost_usd != null && result.estimated_cost_usd > 0 ? `est_cost=${formatUsd(result.estimated_cost_usd)}` : "",
    ].filter(Boolean);
    setHealthStatus("slideUpscale", "ok", "Reachable", metaParts.join(" | "));
    showButtonSuccess(el.slideUpscaleHealthCheck, "OK");
    return;
  }
  const meta = [result.error_type || "Error", result.error_message || result.message || "Slide Upscale API check failed."]
    .filter(Boolean)
    .join(" | ");
  setHealthStatus("slideUpscale", "error", "Failed", meta);
}

export async function testTtsHealth() {
  setHealthStatus("tts", "pending", "Testing...", "");
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
    setHealthStatus("tts", "ok", "Reachable", meta);
    showButtonSuccess(el.ttsHealthCheck, "OK");
    return;
  }
  const meta = [
    result.error_type || "Error",
    result.error_message || result.message || "TTS API check failed.",
  ].filter(Boolean).join(" | ");
  setHealthStatus("tts", "error", "Failed", meta);
}
