<template>
  <section class="card">
    <div v-if="authResultMsg" :class="['gdrive-auth-result', authResultOk ? 'is-ok' : 'is-error']">
      {{ authResultMsg }}
    </div>

    <!-- Global Main Block -->
    <section class="settings-global-block" aria-label="Main settings">
      <div class="settings-global-head">Main</div>
      <div class="settings-list settings-global-list">
        <div class="settings-row">
          <label class="settings-key">Google Cloud Auth</label>
          <div class="settings-value gdrive-auth-row">
            <span v-if="gcloudLoading" class="gdrive-auth-label is-loading"><span class="auth-spinner"></span> Checking...</span>
            <span v-else-if="gcloudStatus.configured" class="gdrive-auth-label is-ok">{{ gcloudStatus.email }}</span>
            <span v-else class="gdrive-auth-label is-warning">Not configured</span>
            <a href="/api/gcloud/auth/start" class="btn-sm">
              {{ gcloudStatus.configured ? 'Re-authenticate' : 'Authenticate' }}
            </a>
          </div>
        </div>
        <div class="settings-row">
          <label class="settings-key" for="google_speech_language_codes">GOOGLE_SPEECH_LANGUAGE_CODES</label>
          <div class="settings-value"><input id="google_speech_language_codes" type="text" v-model="f.GOOGLE_SPEECH_LANGUAGE_CODES" /></div>
        </div>
        <TtsLanguageSelector
          :options="store.ttsLanguageOptions"
          :model-value="f.GOOGLE_TTS_LANGUAGE_CODE"
          :search-text="store.ttsLanguageSearchText"
          :disabled="!languageSelectionEnabled"
          @update:model-value="onTtsLanguageChange"
          @update:search-text="store.ttsLanguageSearchText = $event"
        />
      </div>
    </section>

    <div class="step-sections">
      <StepSection title="Slide Detection" subtitle="Detects slide changes and exports stable ROI and full-frame keyframes from the source video." :forced="true" v-model:expanded="expanded.slideDetection">
        <SlideDetectionSettings />
      </StepSection>

      <StepSection title="Transcription" subtitle="Transcribes the source video into timestamped transcript segments for downstream translation and mapping." :forced="true" v-model:expanded="expanded.transcription">
        <TranscriptionSettings @field-change="onFieldStateChange" />
      </StepSection>

      <StepSection title="Transcript Translate" subtitle="Translates transcript segments 1:1 into the target language before slide mapping." v-model:enabled="f.RUN_STEP_TEXT_TRANSLATE" v-model:expanded="expanded.textTranslate" @update:enabled="onFieldStateChange">
        <TranscriptTranslateSettings />
      </StepSection>

      <StepSection title="Transcript Mapping" subtitle="Maps transcript segments onto detected slide windows and prepares per-slide text assignments." :forced="true" v-model:expanded="expanded.transcriptMapping">
        <TranscriptMappingSettings />
      </StepSection>

      <StepSection title="Finalize Slides" subtitle="Speaker filtering and automatic source selection always run." :forced="true" v-model:expanded="expanded.finalizeSlides">
        <FinalizeSlidesSettings />
      </StepSection>

      <StepSection title="Slide Edit" subtitle="Cleans up the final slide set after speaker filtering." v-model:enabled="f.RUN_STEP_EDIT" v-model:expanded="expanded.edit" @update:enabled="onFieldStateChange">
        <SlideEditSettings />
      </StepSection>

      <StepSection title="Slide Translate" subtitle="Translates the final slide images via nano banana or Google OCR + Glossary rendering." v-model:enabled="f.RUN_STEP_TRANSLATE" v-model:expanded="expanded.translate" @update:enabled="onFieldStateChange">
        <SlideTranslateSettings @field-change="onFieldStateChange" />
      </StepSection>

      <StepSection title="Slide Upscale" subtitle="Upscales the final slide set locally or via Replicate to x4." v-model:enabled="f.RUN_STEP_UPSCALE" v-model:expanded="expanded.upscale" @update:enabled="onFieldStateChange">
        <SlideUpscaleSettings @field-change="onFieldStateChange" />
      </StepSection>

      <StepSection title="TTS" subtitle="Generates a continuous transcript voiceover and aligns it back to the slides." v-model:enabled="f.RUN_STEP_TTS" v-model:expanded="expanded.tts" @update:enabled="onFieldStateChange">
        <TtsSettings />
      </StepSection>

      <StepSection title="Video Export" subtitle="Builds a new MP4 with SRT and timeline from the final slides and voiceover." v-model:enabled="f.RUN_STEP_VIDEO_EXPORT" v-model:expanded="expanded.videoExport" @update:enabled="onFieldStateChange">
        <VideoExportSettings />
      </StepSection>

      <StepSection title="Backup" subtitle="Uploads all output files from the current run to a Google Drive folder." v-model:enabled="f.RUN_STEP_BACKUP" v-model:expanded="expanded.backup" @update:enabled="onFieldStateChange">
        <BackupSettings :gdrive-status="gdriveStatus" :gdrive-loading="gdriveLoading" />
      </StepSection>

      <StepSection title="Test APIs" subtitle="Test each pipeline API endpoint individually." :forced="true" v-model:expanded="expanded.testApis">
        <TestApisSettings />
      </StepSection>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref, computed, watch, onMounted } from "vue";
import { configStore as store, findTtsLanguageOptionByCode } from "../stores/configStore.js";
import StepSection from "../components/StepSection.vue";
import TtsLanguageSelector from "../components/TtsLanguageSelector.vue";

import SlideDetectionSettings from "./settings/SlideDetectionSettings.vue";
import TranscriptionSettings from "./settings/TranscriptionSettings.vue";
import TranscriptTranslateSettings from "./settings/TranscriptTranslateSettings.vue";
import TranscriptMappingSettings from "./settings/TranscriptMappingSettings.vue";
import FinalizeSlidesSettings from "./settings/FinalizeSlidesSettings.vue";
import SlideEditSettings from "./settings/SlideEditSettings.vue";
import SlideTranslateSettings from "./settings/SlideTranslateSettings.vue";
import SlideUpscaleSettings from "./settings/SlideUpscaleSettings.vue";
import TtsSettings from "./settings/TtsSettings.vue";
import VideoExportSettings from "./settings/VideoExportSettings.vue";
import BackupSettings from "./settings/BackupSettings.vue";
import TestApisSettings from "./settings/TestApisSettings.vue";

const f = store.form;

const EXPANDED_KEY = "settings-expanded";
const defaultExpanded = {
  slideDetection: false,
  transcription: false,
  textTranslate: false,
  transcriptMapping: false,
  finalizeSlides: false,
  edit: false,
  translate: false,
  upscale: false,
  tts: false,
  videoExport: false,
  backup: false,
  testApis: false,
};
function loadExpanded() {
  try {
    const saved = JSON.parse(localStorage.getItem(EXPANDED_KEY));
    if (saved && typeof saved === "object") return { ...defaultExpanded, ...saved };
  } catch { /* ignore */ }
  return { ...defaultExpanded };
}
const expanded = reactive(loadExpanded());
watch(() => ({ ...expanded }), (val) => {
  localStorage.setItem(EXPANDED_KEY, JSON.stringify(val));
});

const googleTranscription = computed(() => f.TRANSCRIPTION_PROVIDER === "google_chirp_3");
const languageSelectionEnabled = computed(() => f.RUN_STEP_TRANSLATE || f.RUN_STEP_TEXT_TRANSLATE || f.RUN_STEP_TTS || googleTranscription.value);

function onTtsLanguageChange(code) {
  f.GOOGLE_TTS_LANGUAGE_CODE = code;
  const opt = findTtsLanguageOptionByCode(code);
  if (opt) f.FINAL_SLIDE_TARGET_LANGUAGE = opt.label;
}

function onFieldStateChange() {
  document.dispatchEvent(new CustomEvent("health-stt-sync", { detail: { googleTranscription: googleTranscription.value } }));
}

// Google Cloud ADC auth (for Gemini, TTS, Vision, etc.)
const gcloudStatus = ref({ configured: false, email: "" });
const gcloudLoading = ref(true);

async function fetchGcloudStatus() {
  gcloudLoading.value = true;
  try {
    const res = await fetch("/api/gcloud/status");
    if (res.ok) gcloudStatus.value = await res.json();
  } catch { /* ignore */ }
  gcloudLoading.value = false;
}

// Google Drive auth (separate, for Backup step)
const gdriveStatus = ref({ authenticated: false, email: "" });
const gdriveLoading = ref(true);

async function fetchGdriveStatus() {
  gdriveLoading.value = true;
  try {
    const res = await fetch("/api/gdrive/status");
    if (res.ok) gdriveStatus.value = await res.json();
  } catch { /* ignore */ }
  gdriveLoading.value = false;
}

const authResultMsg = ref("");
const authResultOk = ref(false);

onMounted(() => {
  fetchGcloudStatus();
  fetchGdriveStatus();
  const params = new URLSearchParams(location.search);
  if (params.has("gcloud_auth")) {
    const ok = params.get("gcloud_auth") === "done";
    authResultMsg.value = ok ? "Google Cloud auth: done" : "Google Cloud auth: failed";
    authResultOk.value = ok;
    history.replaceState(null, "", location.pathname);
  } else if (params.has("gdrive_auth")) {
    const ok = params.get("gdrive_auth") === "done";
    authResultMsg.value = ok ? "Google Drive auth: done" : "Google Drive auth: failed";
    authResultOk.value = ok;
    history.replaceState(null, "", location.pathname);
  }
});

watch(googleTranscription, () => {
  onFieldStateChange();
});
</script>
