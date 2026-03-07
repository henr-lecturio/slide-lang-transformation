<template>
  <div class="home-top">
    <section class="card home-top-card run-control-card">
      <h2>Run Control</h2>
      <div class="row wrap">
        <button ref="startBtn" :disabled="isBusyRun || !hasVideo" @click="onStartRun">Start New Run</button>
        <button ref="refreshBtn" @click="onRefreshRuns">Refresh Runs</button>
        <button @click="onPickVideo">Select Video</button>
      </div>
      <section class="quick-settings-panel" aria-label="Quick Settings">
        <div class="quick-settings-head">Quick Settings</div>
        <div class="quick-settings-grid">
          <label class="quick-setting-field" for="home_target_language">
            <h4>Target Language</h4>
            <select id="home_target_language" v-model="homeTargetLanguage" @change="applyQuickSettings">
              <option v-if="config.ttsLanguageOptions.length === 0" value="">No languages</option>
              <option v-for="item in config.ttsLanguageOptions" :key="item.tts_language_code" :value="item.tts_language_code">{{ item.label || item.tts_language_code }}</option>
            </select>
          </label>
          <label class="quick-setting-field" for="home_transcription_provider">
            <h4>Transcription Model</h4>
            <select id="home_transcription_provider" v-model="f.TRANSCRIPTION_PROVIDER" @change="applyQuickSettings">
              <option value="whisper">whisper</option>
              <option value="google_chirp_3">google_chirp_3</option>
            </select>
          </label>
          <label class="quick-setting-field" for="home_gemini_text_translate_model">
            <h4>Transcript Translate Model</h4>
            <select id="home_gemini_text_translate_model" v-model="f.TRANSCRIPT_TRANSLATE_MODEL" @change="applyQuickSettings">
              <option value="gemini-2.5-pro">gemini-2.5-pro</option>
              <option value="general/translation-llm">general/translation-llm</option>
            </select>
          </label>
          <label class="quick-setting-field" for="home_gemini_edit_model">
            <h4>Slide Edit Model</h4>
            <select id="home_gemini_edit_model" v-model="f.GEMINI_EDIT_MODEL" @change="applyQuickSettings">
              <option value="gemini-3.1-flash-image-preview">gemini-3.1-flash-image-preview</option>
              <option value="gemini-3-pro-image-preview">gemini-3-pro-image-preview</option>
              <option value="gemini-2.5-flash-image">gemini-2.5-flash-image</option>
            </select>
          </label>
          <label class="quick-setting-field" for="home_gemini_translate_model">
            <h4>Slide Translate Model</h4>
            <select id="home_gemini_translate_model" v-model="f.GEMINI_TRANSLATE_MODEL" @change="applyQuickSettings">
              <option value="gemini-3.1-flash-image-preview">gemini-3.1-flash-image-preview</option>
              <option value="gemini-3-pro-image-preview">gemini-3-pro-image-preview</option>
              <option value="gemini-2.5-flash-image">gemini-2.5-flash-image</option>
            </select>
          </label>
          <label class="quick-setting-field" for="home_final_slide_upscale_mode">
            <h4>Slide Upscale Model</h4>
            <select id="home_final_slide_upscale_mode" v-model="f.FINAL_SLIDE_UPSCALE_MODE" @change="applyQuickSettings">
              <option value="none">none</option>
              <option value="swin2sr">swin2sr</option>
              <option value="replicate_nightmare_realesrgan">replicate_nightmare_realesrgan</option>
            </select>
          </label>
          <label class="quick-setting-field" for="home_gemini_tts_model">
            <h4>TTS Model</h4>
            <select id="home_gemini_tts_model" v-model="f.GEMINI_TTS_MODEL" @change="applyQuickSettings">
              <option value="gemini-2.5-flash-tts">gemini-2.5-flash-tts</option>
              <option value="gemini-2.5-pro-tts">gemini-2.5-pro-tts</option>
            </select>
          </label>
        </div>
      </section>
      <div class="image-wrap video-preview-wrap">
        <img v-if="videoThumb" :src="videoThumb" alt="Selected video thumbnail" style="cursor: zoom-in" @click="$emit('open-image', videoThumb, videoPathLabel)" />
        <img v-else alt="Selected video thumbnail" />
      </div>
      <div class="muted">{{ videoPathLabel }}</div>
    </section>

    <section class="card home-top-card status-panel-card">
      <div class="status-card-head">
        <div class="status-head-copy">
          <h2>Status</h2>
          <div class="muted">{{ statusSummary }}</div>
        </div>
        <div class="status-actions">
          <button type="button" @click="statusModalOpen = true">Open Terminal</button>
          <button type="button" :disabled="runs.currentRunStatus !== 'running'" @click="onStopRun">{{ runs.currentRunStatus === 'stopping' ? 'Stopping...' : 'Stop Run' }}</button>
          <button type="button" :disabled="runs.currentRunStatus !== 'error' && runs.currentRunStatus !== 'stopped'" @click="onRetryRun">Retry</button>
        </div>
      </div>
      <div class="step-list" aria-live="polite">
        <div v-for="step in runs.currentRunSteps" :key="step.id || step.label" :class="['step-item', 'is-' + (step.status || 'pending')]">
          <span :class="['step-icon', 'is-' + (step.status || 'pending')]" aria-hidden="true"></span>
          <div class="step-body">
            <div class="step-head">
              <span class="step-label">{{ step.label || step.id || 'Step' }}</span>
              <span class="step-state">{{ step.status || 'pending' }}</span>
            </div>
            <div class="step-detail">{{ step.detail || ' ' }}</div>
          </div>
        </div>
      </div>
    </section>
  </div>

  <section class="card home-main">
    <h2>Latest Output</h2>
    <section class="output-info-panel" :class="{ 'is-open': runs.latestInfoExpanded }">
      <button class="output-info-toggle" type="button" :aria-expanded="runs.latestInfoExpanded ? 'true' : 'false'" @click="runs.latestInfoExpanded = !runs.latestInfoExpanded">
        <span>Run Details</span>
        <span class="step-section-chevron" aria-hidden="true"></span>
      </button>
      <div class="output-info-body" :hidden="!runs.latestInfoExpanded">
        <RunInfoGrid :detail="runs.latestRunDetail" />
      </div>
    </section>
    <section class="output-link-section">
      <div class="output-link-heading">Artifacts</div>
      <DownloadLinks :detail="runs.latestRunDetail" :include-video="false" :include-non-video="true" />
    </section>
    <section class="output-link-section">
      <div class="output-link-heading">Video Export</div>
      <DownloadLinks :detail="runs.latestRunDetail" :include-video="true" :include-non-video="false" />
    </section>
    <div class="row wrap">
      <label>View
        <select v-model="runs.latestSlidesMode">
          <option value="final">final_slide_images</option>
          <option value="base">base_events</option>
        </select>
      </label>
      <label>ROI Source
        <select v-model="runs.latestFinalSourceMode">
          <option value="processed">processed</option>
          <option value="raw">raw</option>
          <option value="translated">translated</option>
        </select>
      </label>
      <label>Display
        <select v-model="runs.latestFinalDisplayMode">
          <option value="single">single</option>
          <option value="compare">compare</option>
        </select>
      </label>
    </div>
    <label class="toggle-small">
      <input type="checkbox" v-model="runs.latestShowOriginalText" />
      <span>Show Original Text</span>
    </label>
    <SlideList
      :run-id="runs.latestRunId"
      :slides-mode="runs.latestSlidesMode"
      :source-mode="runs.latestFinalSourceMode"
      :display-mode="runs.latestFinalDisplayMode"
      :show-original-text="runs.latestShowOriginalText"
      :refresh-key="latestRefreshKey"
      @open-image="(url, name) => $emit('open-image', url, name)"
      @set-image-mode="onSetImageMode"
    />
  </section>

  <LogTerminal :open="statusModalOpen" title="Run Terminal" :logs="runs.logTail" @close="statusModalOpen = false" />
</template>

<script setup>
import { ref, computed, inject } from "vue";
import { configStore as config, videoThumbUrl, formatRunIdLabel, saveConfig, findTtsLanguageOptionByCode } from "../stores/configStore.js";
import { runStore as runs, startRun, stopRun, retryRun, loadRuns, setFinalSlideImageMode } from "../stores/runStore.js";
import { showButtonSuccess } from "../composables/useButtonSuccess.js";
import RunInfoGrid from "../components/RunInfoGrid.vue";
import DownloadLinks from "../components/DownloadLinks.vue";
import SlideList from "../components/SlideList.vue";
import LogTerminal from "../components/LogTerminal.vue";

const f = config.form;
const runTask = inject("runTask");
const emit = defineEmits(["open-image", "pick-video"]);

const statusModalOpen = ref(false);
const latestRefreshKey = ref(0);
const homeTargetLanguage = ref("");
const startBtn = ref(null);
const refreshBtn = ref(null);

const hasVideo = computed(() => Boolean((config.selectedVideoPath || "").trim()));
const isBusyRun = computed(() => runs.currentRunStatus === "running" || runs.currentRunStatus === "stopping");

const videoThumb = computed(() => {
  const path = config.selectedVideoPath;
  return path ? videoThumbUrl(path) : "";
});

const videoPathLabel = computed(() => {
  const path = config.selectedVideoPath;
  return path ? `VIDEO_PATH: ${path}` : "VIDEO_PATH: (nicht gesetzt)";
});

const statusSummary = computed(() => {
  const runId = runs.currentRunId ? `, run ${formatRunIdLabel(runs.currentRunId)}` : "";
  return `status: ${runs.currentRunStatus}${runId}`;
});

// Sync homeTargetLanguage from config
import { watch } from "vue";
watch(() => f.GOOGLE_TTS_LANGUAGE_CODE, (code) => {
  homeTargetLanguage.value = code;
}, { immediate: true });

async function applyQuickSettings() {
  // Sync target language back to settings
  const wantedCode = homeTargetLanguage.value;
  const wanted = config.ttsLanguageOptions.find((item) => item.tts_language_code === wantedCode);
  if (wanted) {
    f.GOOGLE_TTS_LANGUAGE_CODE = wanted.tts_language_code;
    f.FINAL_SLIDE_TARGET_LANGUAGE = wanted.label;
  }
  await runTask(saveConfig);
}

async function onStartRun() {
  await runTask(async () => {
    await startRun();
    showButtonSuccess(startBtn.value, "Started");
  });
}

async function onStopRun() {
  await runTask(stopRun);
}

async function onRetryRun() {
  await runTask(retryRun);
}

async function onRefreshRuns() {
  await runTask(async () => {
    await loadRuns();
    showButtonSuccess(refreshBtn.value, "Refreshed");
  });
}

function onPickVideo() {
  emit("pick-video");
}

async function onSetImageMode(runId, eventId, mode) {
  await setFinalSlideImageMode(runId, eventId, mode);
  latestRefreshKey.value++;
}
</script>
