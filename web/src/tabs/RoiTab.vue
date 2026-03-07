<template>
  <div class="roi-layout">
    <section class="card roi-sidebar-card">
      <div class="all-runs-head">
        <h2>ROI</h2>
      </div>
      <div class="settings-list roi-settings-list">
        <SettingsRow label="ROI_X0" field-id="roi_x0"><input id="roi_x0" type="number" v-model="f.ROI_X0" /></SettingsRow>
        <SettingsRow label="ROI_Y0" field-id="roi_y0"><input id="roi_y0" type="number" v-model="f.ROI_Y0" /></SettingsRow>
        <SettingsRow label="ROI_X1" field-id="roi_x1"><input id="roi_x1" type="number" v-model="f.ROI_X1" /></SettingsRow>
        <SettingsRow label="ROI_Y1" field-id="roi_y1"><input id="roi_y1" type="number" v-model="f.ROI_Y1" /></SettingsRow>
        <SettingsRow label="Time (sec)" field-id="overlay-time"><input id="overlay-time" type="number" step="0.1" v-model.number="overlayTime" /></SettingsRow>
      </div>
      <div class="roi-actions">
        <AppButton ref="saveRoiBtn" @click="onSaveRoi">Save ROI</AppButton>
        <AppButton @click="$emit('pick-video')">Select Video</AppButton>
        <span class="muted" aria-live="polite">{{ config.configMeta }}</span>
      </div>
    </section>

    <section class="card roi-detail-card">
      <div class="all-runs-head">
        <h2>ROI Overlay</h2>
        <div class="status-actions">
          <AppButton @click="roiTerminalOpen = true">Open Terminal</AppButton>
        </div>
      </div>
      <div class="row wrap">
        <AppButton ref="genOverlayBtn" :disabled="!hasVideo" @click="onRegenOverlay">Generate Overlay</AppButton>
        <AppButton ref="refreshOverlayBtn" @click="onRefreshOverlay">Refresh Image</AppButton>
      </div>
      <ImagePreview :src="overlayUrl" alt="ROI overlay preview" :zoom-src="overlayRawUrl" :zoom-caption="overlayName" />
    </section>
  </div>

  <LogTerminal :open="roiTerminalOpen" title="ROI Terminal" :logs="roiLogs" @close="roiTerminalOpen = false" />
</template>

<script setup>
import { ref, computed, inject } from "vue";
import { configStore as config, saveConfig } from "../stores/configStore.js";
import { apiGet, apiPost } from "../composables/useApi.js";
import AppButton from "../components/AppButton.vue";
import SettingsRow from "../components/SettingsRow.vue";
import ImagePreview from "../components/ImagePreview.vue";
import LogTerminal from "../components/LogTerminal.vue";

const f = config.form;
const runTask = inject("runTask");
const emit = defineEmits(["pick-video", "open-image"]);

const overlayTime = ref(30);
const overlayUrl = ref("");
const overlayRawUrl = ref("");
const overlayName = ref("roi_overlay.png");
const roiLogs = ref([]);
const roiTerminalOpen = ref(false);
const saveRoiBtn = ref(null);
const genOverlayBtn = ref(null);
const refreshOverlayBtn = ref(null);

const hasVideo = computed(() => Boolean((config.selectedVideoPath || "").trim()));

async function loadOverlay() {
  const data = await apiGet("/api/overlay");
  if (!data.exists) {
    overlayUrl.value = "";
    overlayRawUrl.value = "";
    return;
  }
  const v = data.mtime || Date.now();
  overlayUrl.value = `${data.url}?v=${v}`;
  overlayRawUrl.value = data.url;
  overlayName.value = String(data.url || "").split("/").pop() || "roi_overlay.png";
}

async function onSaveRoi() {
  await runTask(async () => {
    await saveConfig();
    saveRoiBtn.value?.flashSuccess("Saved");
  });
}

async function onRegenOverlay() {
  await runTask(async () => {
    const t = Number(overlayTime.value || 30);
    const result = await apiPost("/api/overlay", { time_sec: t });
    if (result.output) {
      roiLogs.value = String(result.output).trim().split("\n");
    }
    await loadOverlay();
    genOverlayBtn.value?.flashSuccess("Generated");
  });
}

async function onRefreshOverlay() {
  await runTask(async () => {
    await loadOverlay();
    refreshOverlayBtn.value?.flashSuccess("Refreshed");
  });
}

defineExpose({ loadOverlay });
</script>
