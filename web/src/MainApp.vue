<template>
  <TabNav ref="tabNavRef" :active-tab="activeTab" @switch="setActiveTab" @save="onSaveSettings" />

  <main>
    <section class="panel" :class="{ active: activeTab === 'home' }">
      <HomeTab
        @open-image="openImage"
        @pick-video="openVideoPicker"
      />
    </section>

    <section class="panel" :class="{ active: activeTab === 'all-runs' }">
      <AllRunsTab @open-image="openImage" />
    </section>

    <section id="panel-lab" class="panel" :class="{ active: activeTab === 'lab' }">
      <div id="lab-app"></div>
    </section>

    <section class="panel" :class="{ active: activeTab === 'roi' }">
      <RoiTab
        ref="roiTabRef"
        @pick-video="openVideoPicker"
        @open-image="openImage"
      />
    </section>

    <section class="panel" :class="{ active: activeTab === 'settings' }">
      <SettingsTab />
    </section>
  </main>

  <ImageModal
    :open="imageModal.open"
    :src="imageModal.src"
    :caption="imageModal.caption"
    @close="imageModal.open = false"
  />

  <VideoPickerModal
    :open="videoPicker.open"
    :items="videoPicker.items"
    :selected-path="config.selectedVideoPath"
    @close="videoPicker.open = false"
    @select="onVideoSelect"
  />
</template>

<script setup>
import { ref, reactive, provide, onMounted } from "vue";
import { configStore as config, loadConfig, saveConfig } from "./stores/configStore.js";
import { runStore, loadRuns, pollCurrent, deriveLatestAutoPreview, shouldAutoPreviewLatest } from "./stores/runStore.js";
import { apiGet } from "./composables/useApi.js";
import { usePolling } from "./composables/usePolling.js";
import { showButtonSuccess } from "./composables/useButtonSuccess.js";
import TabNav from "./components/TabNav.vue";
import HomeTab from "./tabs/HomeTab.vue";
import AllRunsTab from "./tabs/AllRunsTab.vue";
import RoiTab from "./tabs/RoiTab.vue";
import SettingsTab from "./tabs/SettingsTab.vue";
import ImageModal from "./components/ImageModal.vue";
import VideoPickerModal from "./components/VideoPickerModal.vue";

const ACTIVE_TAB_STORAGE_KEY = "slide-transform-active-tab";

const activeTab = ref(getInitialActiveTab());
const roiTabRef = ref(null);
const tabNavRef = ref(null);

const imageModal = reactive({ open: false, src: "", caption: "" });
const videoPicker = reactive({ open: false, items: [] });

let busy = false;
async function runTask(fn) {
  if (busy) return;
  busy = true;
  try {
    await fn();
  } catch (err) {
    alert(err.message || String(err));
  } finally {
    busy = false;
  }
}

provide("runTask", runTask);

function getInitialActiveTab() {
  try {
    const stored = window.localStorage.getItem(ACTIVE_TAB_STORAGE_KEY) || "";
    if (["image-lab", "export-lab", "consistency-lab"].includes(stored)) return "lab";
    if (["home", "all-runs", "lab", "roi", "settings"].includes(stored)) return stored;
  } catch {}
  return "home";
}

function setActiveTab(tabName) {
  const allowed = new Set(["home", "all-runs", "lab", "roi", "settings"]);
  activeTab.value = allowed.has(tabName) ? tabName : "home";
  try {
    window.localStorage.setItem(ACTIVE_TAB_STORAGE_KEY, activeTab.value);
  } catch {}
}

function openImage(url, name) {
  imageModal.src = url;
  imageModal.caption = name || "";
  imageModal.open = true;
}

// Expose globally for LabApp (separate Vue app) to open image modal
window.__openImageModal = openImage;

async function openVideoPicker() {
  const data = await apiGet("/api/videos");
  videoPicker.items = data.items || [];
  if (data.selected_video) {
    config.selectedVideoPath = data.selected_video;
  }
  videoPicker.open = true;
}

async function onVideoSelect(path) {
  config.selectedVideoPath = path;
  await runTask(async () => {
    await saveConfig();
    videoPicker.open = false;
  });
}

async function onSaveSettings() {
  await runTask(async () => {
    await saveConfig();
    config.configMeta = "Settings saved.";
    showButtonSuccess(tabNavRef.value?.saveBtn, "Saved");
  });
}

// Apply auto-preview for latest run
function applyAutoPreview() {
  if (shouldAutoPreviewLatest(runStore.latestRunDetail)) {
    const preview = deriveLatestAutoPreview(runStore.latestRunDetail);
    if (preview) {
      runStore.latestSlidesMode = preview.slidesMode;
      if (preview.slidesMode === "final") {
        runStore.latestFinalSourceMode = preview.sourceMode;
      }
    }
  }
}

onMounted(async () => {
  await runTask(loadConfig);
  if (roiTabRef.value?.loadOverlay) {
    await runTask(() => roiTabRef.value.loadOverlay());
  }
  await runTask(loadRuns);
  applyAutoPreview();
});

usePolling(pollCurrent, 2000);
</script>
