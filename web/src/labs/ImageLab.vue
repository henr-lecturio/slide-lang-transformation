<template>
  <LabAccordion name="imageLab" :start-open="true">
    <template #title>Image Lab</template>

    <LabToolbar
      :status="status"
      :has-selection="hasImage"
      idle-label="No image selected"
      @open-terminal="terminalOpen = true"
      @stop="stopJob"
    >
      <template #actions>
        <AppButton :disabled="isBusy" @click="openPicker">Select Image</AppButton>
        <AppButton :disabled="isBusy" @click="openSettings">Test Settings</AppButton>
        <AppButton :disabled="isBusy || !hasImage" @click="runAction('edit')">Test Slide Edit</AppButton>
        <AppButton :disabled="isBusy || !hasImage" @click="runAction('translate')">Test Slide Translate</AppButton>
        <AppButton :disabled="isBusy || !hasImage" @click="runAction('upscale')">Test Slide Upscale</AppButton>
      </template>
    </LabToolbar>

    <div class="lab-preview-grid">
      <section class="lab-preview-panel">
        <div class="lab-preview-label-row">
          <div class="slide-compare-label">Original</div>
          <div class="muted lab-selection-meta">{{ selectionMeta }}</div>
        </div>
        <ImagePreview :src="originalImageUrl" alt="Selected lab input image" :zoom-src="selectedImage?.image_url" :zoom-caption="selectedImage?.name || 'lab-input'" wrap-class="lab-preview-wrap" />
      </section>
      <section class="lab-preview-panel">
        <div class="lab-preview-label-row">
          <div class="slide-compare-label">Result</div>
          <div class="lab-result-view-toggle" role="group" aria-label="Image Lab result view">
            <button
              :class="['lab-result-view-btn', { 'is-active': resultViewMode === 'result' }]"
              type="button"
              @click="resultViewMode = 'result'"
            >Result</button>
            <button
              :class="['lab-result-view-btn', { 'is-active': resultViewMode === 'ocr_debug' }]"
              type="button"
              :disabled="!debugAvailable"
              @click="resultViewMode = 'ocr_debug'"
            >OCR Debug</button>
          </div>
        </div>
        <ImagePreview :src="resultImageUrl" alt="Latest lab result image" :zoom-src="resolvedResultUrl" :zoom-caption="resolvedResultName" wrap-class="lab-preview-wrap" />
      </section>
    </div>

    <PickerModal
      :open="pickerOpen"
      title="Select Image"
      :items="images"
      :label-fn="imageLabel"
      :item-key="(item) => `${item.run_id}_${item.event_id}`"
      :is-selected="(item) => selectedImage && item.run_id === selectedImage.run_id && item.event_id === selectedImage.event_id"
      empty-text="No final_slide_images found in the latest run."
      @close="pickerOpen = false"
      @select="selectImage"
    />

    <ImageLabSettings
      ref="settingsRef"
      :open="settingsOpen"
      :tts-language-options="ttsLanguageOptions"
      @close="settingsOpen = false"
      @save="onSettingsSave"
      @save-to-main="onSaveToMain"
    />

    <LogTerminal
      :open="terminalOpen"
      title="Image Lab Terminal"
      :logs="logs"
      @close="terminalOpen = false"
    />
  </LabAccordion>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import LabAccordion from "../components/LabAccordion.vue";
import LabToolbar from "../components/LabToolbar.vue";
import AppButton from "../components/AppButton.vue";
import ImagePreview from "../components/ImagePreview.vue";
import PickerModal from "../components/PickerModal.vue";
import LogTerminal from "../components/LogTerminal.vue";
import ImageLabSettings from "./ImageLabSettings.vue";
import { apiGet, apiPost } from "../composables/useApi.js";
import { useLabStatus } from "../composables/useLabStatus.js";
import { formatRunIdLabel } from "../stores/configStore.js";

const selectedImage = ref(null);
const images = ref([]);
const pickerOpen = ref(false);
const settingsOpen = ref(false);
const terminalOpen = ref(false);
const settingsRef = ref(null);
const resultViewMode = ref("result");
const ttsLanguageOptions = ref([]);
const cacheKey = ref(Date.now());

const { status, currentData, logs, isBusy, setStatus } = useLabStatus({
  faviconLabel: "lab",
  statusEndpoint: "/api/lab/status",
  onUpdate(data) {
    cacheKey.value = Date.now();
    if (!selectedImage.value && data?.original_url && data?.run_id) {
      selectedImage.value = {
        run_id: data.run_id,
        event_id: data.event_id,
        image_url: data.original_url,
        name: data.input_name || "lab-input",
      };
    }
  },
});

const hasImage = computed(() => Boolean(selectedImage.value?.image_url));

const selectionMeta = computed(() => {
  const item = selectedImage.value;
  if (!item) return "";
  return `| selected: ${formatRunIdLabel(item.run_id)}, event ${item.event_id || "-"}`;
});

const originalImageUrl = computed(() => {
  const item = selectedImage.value;
  if (!item?.image_url) {
    const cur = currentData.value;
    if (cur?.original_url) return `${cur.original_url}?v=${cacheKey.value}`;
    return "";
  }
  return `${item.image_url}?v=${cacheKey.value}`;
});

const debugAvailable = computed(() => Boolean(String(currentData.value?.result_debug_overlay_url || "").trim()));

const resolvedResultUrl = computed(() => {
  const cur = currentData.value;
  if (!cur) return "";
  if (resultViewMode.value === "ocr_debug" && debugAvailable.value) {
    return String(cur.result_debug_overlay_url || "").trim();
  }
  return String(cur.result_url || "").trim();
});

const resolvedResultName = computed(() => {
  const cur = currentData.value;
  if (!cur) return "lab-result";
  if (resultViewMode.value === "ocr_debug" && debugAvailable.value) {
    return String(cur.result_debug_overlay_name || "").trim() || "lab-ocr-debug";
  }
  return String(cur.result_name || "").trim() || "lab-result";
});

const resultImageUrl = computed(() => {
  if (!resolvedResultUrl.value) return "";
  return `${resolvedResultUrl.value}?v=${cacheKey.value}`;
});


async function loadTtsLanguageOptions() {
  try {
    const data = await apiGet("/api/config");
    if (Array.isArray(data.GEMINI_TTS_LANGUAGE_OPTIONS)) {
      ttsLanguageOptions.value = data.GEMINI_TTS_LANGUAGE_OPTIONS;
    }
  } catch { /* ignore */ }
}

async function openPicker() {
  try {
    const data = await apiGet("/api/lab/images");
    images.value = data.items || [];
    if (!selectedImage.value && images.value.length > 0) {
      selectedImage.value = images.value[0];
    }
    pickerOpen.value = true;
  } catch (err) {
    alert(err.message || String(err));
  }
}

function selectImage(item) {
  selectedImage.value = item;
  pickerOpen.value = false;
}

function openSettings() {
  settingsOpen.value = true;
}

onMounted(loadTtsLanguageOptions);

function onSettingsSave() {
  settingsOpen.value = false;
}

function onSaveToMain(settings) {
  // Write lab settings back into main settings form fields
  const el = (id) => document.getElementById(id);
  if (settings.slide_edit_model && el("gemini_edit_model")) el("gemini_edit_model").value = settings.slide_edit_model;
  if (settings.slide_edit_prompt != null && el("gemini_edit_prompt")) el("gemini_edit_prompt").value = settings.slide_edit_prompt;
  if (settings.slide_translate_model && el("gemini_translate_model")) el("gemini_translate_model").value = settings.slide_translate_model;
  if (settings.slide_translate_styles_json && el("slide_translate_styles_json")) el("slide_translate_styles_json").value = settings.slide_translate_styles_json;
  if (settings.slide_upscale_mode && el("final_slide_upscale_mode")) el("final_slide_upscale_mode").value = settings.slide_upscale_mode;
  if (settings.slide_upscale_model && el("final_slide_upscale_model")) el("final_slide_upscale_model").value = settings.slide_upscale_model;
  if (settings.slide_upscale_device && el("final_slide_upscale_device")) el("final_slide_upscale_device").value = settings.slide_upscale_device;
  if (settings.slide_upscale_tile_size != null && el("final_slide_upscale_tile_size")) el("final_slide_upscale_tile_size").value = settings.slide_upscale_tile_size;
  if (settings.slide_upscale_tile_overlap != null && el("final_slide_upscale_tile_overlap")) el("final_slide_upscale_tile_overlap").value = settings.slide_upscale_tile_overlap;
  if (settings.replicate_model_ref && el("replicate_nightmare_realesrgan_model_ref")) el("replicate_nightmare_realesrgan_model_ref").value = settings.replicate_model_ref;
  if (settings.replicate_version_id && el("replicate_nightmare_realesrgan_version_id")) el("replicate_nightmare_realesrgan_version_id").value = settings.replicate_version_id;
  settingsOpen.value = false;
}

async function runAction(action) {
  if (!selectedImage.value) return;
  try {
    currentData.value = null;
    cacheKey.value = Date.now();
    const settings = settingsRef.value?.getSettings() || {};
    const payload = {
      run_id: selectedImage.value.run_id,
      event_id: selectedImage.value.event_id,
      settings,
    };
    const res = await apiPost(`/api/lab/${action}`, payload);
    setStatus(res.current || {});
  } catch (err) {
    alert(err.message || String(err));
  }
}

async function stopJob() {
  try {
    const res = await apiPost("/api/lab/stop", {});
    setStatus(res.current || {});
  } catch (err) {
    alert(err.message || String(err));
  }
}

function imageLabel(item) {
  return `event ${item.event_id} | ${Number(item.slide_start || 0).toFixed(2)}s - ${Number(item.slide_end || 0).toFixed(2)}s | ${item.name}`;
}

</script>
