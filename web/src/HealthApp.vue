<template>
  <div class="settings-list">
    <HealthCheck
      v-for="check in checks"
      :key="check.ref"
      :ref="(el) => { if (el) refs[check.ref] = el }"
      :label="check.label"
      :button-label="check.buttonLabel"
      :endpoint="check.endpoint"
      :payload-fn="check.payloadFn"
      :format-meta="check.formatMeta"
    />
  </div>
</template>

<script setup>
import { onMounted, reactive } from "vue";
import HealthCheck from "./components/HealthCheck.vue";

const refs = reactive({});

function val(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : "";
}

function selectedTtsLanguageLabel() {
  const select = document.getElementById("final_slide_target_language");
  if (!select) return "";
  const opt = select.selectedOptions?.[0];
  if (!opt) return "";
  return opt.dataset.label || opt.textContent.trim();
}

function formatUsd(value) {
  const num = Number(value || 0);
  if (!(num > 0)) return "-";
  return `$${num.toFixed(4)}`;
}

const checks = [
  {
    ref: "gemini",
    label: "Gemini API",
    buttonLabel: "Test Gemini API",
    endpoint: "/api/gemini/health",
    payloadFn: () => ({
      GCLOUD_PROJECT_ID: val("gcloud_project_id"),
      GEMINI_EDIT_MODEL: val("gemini_edit_model"),
    }),
    formatMeta: (r) => [
      `model=${r.model || "-"}`,
      `project=${r.project_id_used || "-"}`,
      `location=${r.location || "-"}`,
      `${r.latency_ms || 0} ms`,
      `${r.image_width || 0}x${r.image_height || 0}`,
      `${r.image_bytes || 0} bytes`,
    ].join(" | "),
  },
  {
    ref: "speechToText",
    label: "Speech-to-Text API",
    buttonLabel: "Test Speech-to-Text API",
    endpoint: "/api/transcription/health",
    payloadFn: () => ({
      GCLOUD_PROJECT_ID: val("gcloud_project_id"),
      TRANSCRIPTION_PROVIDER: val("transcription_provider"),
      GOOGLE_SPEECH_LOCATION: val("google_speech_location"),
      GOOGLE_SPEECH_MODEL: val("google_speech_model"),
      GOOGLE_SPEECH_LANGUAGE_CODES: val("google_speech_language_codes"),
    }),
    formatMeta: (r) => [
      `project=${r.project_id || "-"}`,
      `location=${r.location || "-"}`,
      `model=${r.model || "-"}`,
      `languages=${Array.isArray(r.language_codes) ? r.language_codes.join(",") : "-"}`,
      `${r.latency_ms || 0} ms`,
      `results=${r.results_count || 0}`,
    ].join(" | "),
  },
  {
    ref: "cloudTranslation",
    label: "Cloud Translation API",
    buttonLabel: "Test Cloud Translation API",
    endpoint: "/api/cloud-translation/health",
    payloadFn: () => ({
      GCLOUD_PROJECT_ID: val("gcloud_project_id"),
      GOOGLE_TRANSLATE_LOCATION: val("google_translate_location"),
      GOOGLE_TRANSLATE_SOURCE_LANGUAGE_CODE: val("google_translate_source_language_code"),
      FINAL_SLIDE_TARGET_LANGUAGE: selectedTtsLanguageLabel(),
    }),
    formatMeta: (r) => {
      const translated = String(r.translated_text || "").trim();
      const preview = translated.length > 90 ? `${translated.slice(0, 87)}...` : translated;
      return [
        `project=${r.project_id_used || "-"}`,
        `location=${r.location || "-"}`,
        `model=${r.model || "-"}`,
        `target=${r.target_language_code || "-"}`,
        `${r.latency_ms || 0} ms`,
        preview ? `sample="${preview}"` : "",
      ].filter(Boolean).join(" | ");
    },
  },
  {
    ref: "cloudVision",
    label: "Cloud Vision API",
    buttonLabel: "Test Cloud Vision API",
    endpoint: "/api/cloud-vision/health",
    payloadFn: () => ({
      GCLOUD_PROJECT_ID: val("gcloud_project_id"),
    }),
    formatMeta: (r) => [
      `project=${r.project_id_used || "-"}`,
      `${r.latency_ms || 0} ms`,
      r.ocr_preview ? `ocr="${r.ocr_preview}"` : "",
    ].filter(Boolean).join(" | "),
  },
  {
    ref: "cloudTts",
    label: "Cloud TTS API",
    buttonLabel: "Test Cloud TTS API",
    endpoint: "/api/tts/health",
    payloadFn: () => {
      const select = document.getElementById("final_slide_target_language");
      const selectedOpt = select?.selectedOptions?.[0];
      const ttsCode = selectedOpt?.dataset?.ttsLanguageCode || select?.value || "";
      return {
        GCLOUD_PROJECT_ID: val("gcloud_project_id"),
        GOOGLE_TTS_LANGUAGE_CODE: ttsCode,
        GEMINI_TTS_MODEL: val("gemini_tts_model"),
        GEMINI_TTS_VOICE: val("gemini_tts_voice"),
        GEMINI_TTS_PROMPT: (document.getElementById("gemini_tts_prompt")?.value || ""),
      };
    },
    formatMeta: (r) => [
      `project=${r.project_id_used || "-"}`,
      `voice=${r.voice || "-"}`,
      `model=${r.model || "-"}`,
      `${r.latency_ms || 0} ms`,
      `${r.audio_bytes || 0} bytes`,
      `${r.duration_sec || 0}s`,
    ].join(" | "),
  },
  {
    ref: "replicate",
    label: "Replicate API",
    buttonLabel: "Test Replicate API",
    endpoint: "/api/replicate/health",
    payloadFn: () => ({
      REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF: val("replicate_nightmare_realesrgan_model_ref"),
      REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID: val("replicate_nightmare_realesrgan_version_id"),
      REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND: Number(document.getElementById("replicate_nightmare_realesrgan_price_per_second")?.value || 0),
    }),
    formatMeta: (r) => [
      `model=${r.model || "-"}`,
      r.version_id ? `version=${r.version_id}` : "",
      `x${r.scale || 4}`,
      `${r.latency_ms || 0} ms`,
      `${r.image_width || 0}x${r.image_height || 0}`,
      r.predict_time_sec != null ? `predict=${Number(r.predict_time_sec).toFixed(3)}s` : "",
      r.estimated_cost_usd != null && r.estimated_cost_usd > 0 ? `est_cost=${formatUsd(r.estimated_cost_usd)}` : "",
    ].filter(Boolean).join(" | "),
  },
];

function clearRefs(...keys) {
  for (const k of keys) {
    refs[k]?.clear();
  }
}

onMounted(() => {
  function listen(id, keys) {
    const el = document.getElementById(id);
    if (!el) return;
    const handler = () => clearRefs(...keys);
    el.addEventListener("input", handler);
    el.addEventListener("change", handler);
  }

  // GCLOUD_PROJECT_ID clears all
  listen("gcloud_project_id", ["gemini", "speechToText", "cloudTranslation", "cloudVision", "cloudTts", "replicate"]);

  // Gemini-specific
  listen("gemini_edit_model", ["gemini"]);

  // Speech-to-Text
  for (const id of ["transcription_provider", "google_speech_location", "google_speech_model", "google_speech_language_codes"]) {
    listen(id, ["speechToText"]);
  }

  // Cloud Translation
  for (const id of ["google_translate_location", "google_translate_source_language_code", "final_slide_target_language_search", "final_slide_target_language"]) {
    listen(id, ["cloudTranslation"]);
  }
  const termbaseBody = document.getElementById("termbase-table-body");
  if (termbaseBody) {
    const handler = () => clearRefs("cloudTranslation");
    termbaseBody.addEventListener("input", handler);
    termbaseBody.addEventListener("change", handler);
  }

  // Cloud TTS
  for (const id of ["final_slide_target_language_search", "final_slide_target_language", "gemini_tts_model", "gemini_tts_voice", "gemini_tts_prompt"]) {
    listen(id, ["cloudTts"]);
  }

  // Replicate
  for (const id of ["replicate_nightmare_realesrgan_model_ref", "replicate_nightmare_realesrgan_version_id", "replicate_nightmare_realesrgan_price_per_second"]) {
    listen(id, ["replicate"]);
  }

  // Custom events from vanilla settings.js
  document.addEventListener("health-clear-all", () => {
    clearRefs("gemini", "speechToText", "cloudTranslation", "cloudVision", "cloudTts", "replicate");
  });

  document.addEventListener("health-stt-sync", (e) => {
    const { googleTranscription } = e.detail;
    if (!googleTranscription) {
      refs.speechToText?.setIdle("Only for google_chirp_3.");
    } else if (refs.speechToText?.statusText?.value === "Only for google_chirp_3.") {
      refs.speechToText?.clear();
    }
  });
});
</script>
