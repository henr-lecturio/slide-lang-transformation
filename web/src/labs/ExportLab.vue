<template>
  <LabAccordion name="exportLab">
    <template #title>Export Lab</template>

    <LabToolbar
      :status="status"
      :has-selection="hasRun"
      idle-label="No run selected"
      @open-terminal="terminalOpen = true"
      @stop="stop"
    >
      <template #actions>
        <AppButton :disabled="isBusy" @click="openPicker">Select Run</AppButton>
        <AppButton :disabled="isBusy" @click="openSettings">Test Settings</AppButton>
        <AppButton :disabled="isBusy || !canExport" @click="runExport">Run Export</AppButton>
      </template>
    </LabToolbar>

    <div class="lab-preview-grid">
      <section class="lab-preview-panel">
        <div class="lab-preview-label-row">
          <div class="slide-compare-label">Export Preview</div>
          <div class="muted lab-selection-meta">{{ selectionMeta }}</div>
        </div>
        <div class="image-wrap lab-preview-wrap export-lab-video-wrap">
          <video ref="videoEl" controls preload="metadata"></video>
        </div>
        <div class="summary-links row wrap">
          <template v-for="link in downloadLinks" :key="link.label">
            <a
              v-if="downloadsEnabled && link.url"
              class="summary-link"
              :href="link.url"
              download
            >{{ link.label }}</a>
            <a
              v-else-if="link.url"
              class="summary-link is-disabled"
              aria-disabled="true"
              :tabindex="-1"
            >{{ link.label }}</a>
          </template>
        </div>
      </section>
    </div>

    <PickerModal
      :open="pickerOpen"
      title="Select Run"
      :items="runs"
      :label-fn="runLabel"
      :item-key="(item) => item.run_id"
      :is-selected="(item) => item.run_id === selectedRun?.run_id"
      :is-disabled="(item) => !item.export_ready"
      empty-text="No exportable runs available."
      @close="pickerOpen = false"
      @select="selectRun"
    />

    <ExportLabSettings
      ref="settingsRef"
      :open="settingsOpen"
      @close="settingsOpen = false"
      @save="settingsOpen = false"
    />

    <LogTerminal
      :open="terminalOpen"
      title="Export Lab Terminal"
      :logs="logs"
      @close="terminalOpen = false"
    />
  </LabAccordion>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import LabAccordion from "../components/LabAccordion.vue";
import AppButton from "../components/AppButton.vue";
import LabToolbar from "../components/LabToolbar.vue";
import PickerModal from "../components/PickerModal.vue";
import LogTerminal from "../components/LogTerminal.vue";
import ExportLabSettings from "./ExportLabSettings.vue";
import { apiGet, apiPost } from "../composables/useApi.js";
import { useLabStatus } from "../composables/useLabStatus.js";
import { formatRunIdLabel } from "../stores/configStore.js";

const selectedRun = ref(null);
const runs = ref([]);
const pickerOpen = ref(false);
const settingsOpen = ref(false);
const terminalOpen = ref(false);
const videoEl = ref(null);
const settingsRef = ref(null);
const videoRefreshKey = ref("");

const { status, currentData: current, logs, isBusy, setStatus, stop } = useLabStatus({
  faviconLabel: "export-lab",
  statusEndpoint: "/api/export-lab/status",
  stopEndpoint: "/api/export-lab/stop",
  fallbackPrefix: "Export Lab",
});

const hasRun = computed(() => Boolean(selectedRun.value?.run_id));
const canExport = computed(() => hasRun.value && Boolean(selectedRun.value?.export_ready));

const selectionMeta = computed(() => {
  if (!selectedRun.value) return "";
  return `| selected: ${formatRunIdLabel(selectedRun.value.run_id)}`;
});

const visibleCurrent = computed(() => {
  const sel = selectedRun.value;
  const cur = current.value;
  if (sel?.run_id && cur?.run_id && sel.run_id === cur.run_id) return cur;
  return null;
});

const downloadsEnabled = computed(() => visibleCurrent.value?.status === "done");

const downloadLinks = computed(() => {
  const cur = visibleCurrent.value;
  return [
    { label: "MP4", url: cur?.result_url || "" },
    { label: "Subtitles", url: cur?.subtitle_url || "" },
    { label: "Timeline JSON", url: cur?.timeline_json_url || "" },
    { label: "Timeline CSV", url: cur?.timeline_csv_url || "" },
  ].filter((item) => item.url);
});

function appendCacheKey(url, cacheKey) {
  if (!url) return "";
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}v=${encodeURIComponent(cacheKey)}`;
}

watch(visibleCurrent, (cur) => {
  const video = videoEl.value;
  if (!video) return;
  if (cur?.status === "done" && cur?.result_url) {
    const key = [cur.job_id || "", cur.status || "", cur.finished_at || 0, cur.result_url].join("|");
    if (videoRefreshKey.value !== key) {
      videoRefreshKey.value = key;
      video.pause();
      video.src = appendCacheKey(cur.result_url, cur.finished_at || Date.now());
      video.load();
    }
  } else {
    if (videoRefreshKey.value) {
      videoRefreshKey.value = "";
      video.pause();
      video.removeAttribute("src");
      video.load();
    }
  }
});

async function openPicker() {
  try {
    const data = await apiGet("/api/export-lab/runs");
    runs.value = data.runs || [];
    if (data.current) current.value = data.current;
    if (!selectedRun.value && runs.value.length > 0) {
      selectedRun.value = runs.value.find((item) => item.export_ready) || runs.value[0];
    }
    pickerOpen.value = true;
  } catch (err) {
    alert(err.message || String(err));
  }
}

function selectRun(item) {
  selectedRun.value = item;
  pickerOpen.value = false;
}

function openSettings() {
  settingsOpen.value = true;
}

async function runExport() {
  if (!selectedRun.value?.run_id) return;
  try {
    const settings = settingsRef.value?.getSettings() || {};
    const payload = { run_id: selectedRun.value.run_id, settings };
    const res = await apiPost("/api/export-lab/export", payload);
    setStatus(res.current || res);
  } catch (err) {
    alert(err.message || String(err));
  }
}

function runLabel(item) {
  const parts = [item.label || item.run_id, item.run_status || "-"];
  if (!item.export_ready && Array.isArray(item.missing_requirements) && item.missing_requirements.length > 0) {
    parts.push(`missing: ${item.missing_requirements.join(", ")}`);
  }
  return parts.join(" | ");
}

</script>
