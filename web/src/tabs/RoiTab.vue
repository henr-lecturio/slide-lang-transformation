<template>
  <div class="roi-layout">
    <section class="card roi-sidebar-card">
      <div class="all-runs-head">
        <h2>ROI</h2>
      </div>
      <div class="settings-list roi-settings-list">
        <div class="settings-row">
          <label class="settings-key" for="roi_x0">ROI_X0</label>
          <div class="settings-value"><input id="roi_x0" type="number" v-model="f.ROI_X0" /></div>
        </div>
        <div class="settings-row">
          <label class="settings-key" for="roi_y0">ROI_Y0</label>
          <div class="settings-value"><input id="roi_y0" type="number" v-model="f.ROI_Y0" /></div>
        </div>
        <div class="settings-row">
          <label class="settings-key" for="roi_x1">ROI_X1</label>
          <div class="settings-value"><input id="roi_x1" type="number" v-model="f.ROI_X1" /></div>
        </div>
        <div class="settings-row">
          <label class="settings-key" for="roi_y1">ROI_Y1</label>
          <div class="settings-value"><input id="roi_y1" type="number" v-model="f.ROI_Y1" /></div>
        </div>
        <div class="settings-row">
          <label class="settings-key" for="overlay-time">Time (sec)</label>
          <div class="settings-value"><input id="overlay-time" type="number" step="0.1" v-model.number="overlayTime" /></div>
        </div>
      </div>
      <div class="roi-actions">
        <button ref="saveRoiBtn" @click="onSaveRoi">Save ROI</button>
        <button type="button" @click="$emit('pick-video')">Select Video</button>
        <span class="muted" aria-live="polite">{{ config.configMeta }}</span>
      </div>
    </section>

    <section class="card roi-detail-card">
      <div class="all-runs-head">
        <h2>ROI Overlay</h2>
        <div class="status-actions">
          <button type="button" @click="roiTerminalOpen = true">Open Terminal</button>
        </div>
      </div>
      <div class="row wrap">
        <button ref="genOverlayBtn" :disabled="!hasVideo" @click="onRegenOverlay">Generate Overlay</button>
        <button ref="refreshOverlayBtn" @click="onRefreshOverlay">Refresh Image</button>
      </div>
      <div class="image-wrap">
        <img v-if="overlayUrl" :src="overlayUrl" alt="ROI overlay preview" style="cursor: zoom-in" @click="$emit('open-image', overlayRawUrl, overlayName)" />
        <img v-else alt="ROI overlay preview" />
      </div>
    </section>
  </div>

  <LogTerminal :open="roiTerminalOpen" title="ROI Terminal" :logs="roiLogs" @close="roiTerminalOpen = false" />
</template>

<script setup>
import { ref, computed, inject } from "vue";
import { configStore as config, saveConfig } from "../stores/configStore.js";
import { apiGet, apiPost } from "../composables/useApi.js";
import { showButtonSuccess } from "../composables/useButtonSuccess.js";
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
    showButtonSuccess(saveRoiBtn.value, "Saved");
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
    showButtonSuccess(genOverlayBtn.value, "Generated");
  });
}

async function onRefreshOverlay() {
  await runTask(async () => {
    await loadOverlay();
    showButtonSuccess(refreshOverlayBtn.value, "Refreshed");
  });
}

defineExpose({ loadOverlay });
</script>
