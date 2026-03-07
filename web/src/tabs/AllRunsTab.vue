<template>
  <div class="all-runs-layout">
    <section class="card all-runs-sidebar-card">
      <div class="all-runs-head">
        <h2>All Runs</h2>
      </div>
      <div class="runs-list">
        <div v-if="runs.runs.length === 0" class="muted">No runs yet.</div>
        <RunCard
          v-for="run in runs.runs"
          :key="run.id"
          :run="run"
          :active="run.id === runs.selectedRunId"
          @select="selectRun(run.id)"
        />
      </div>
    </section>

    <section class="card all-runs-detail-card">
      <div class="all-runs-head">
        <h2>Run Details</h2>
      </div>
      <div class="row wrap">
        <label>View
          <select v-model="runs.runSlidesMode">
            <option value="final">final_slide_images</option>
            <option value="base">base_events</option>
          </select>
        </label>
        <label>ROI Source
          <select v-model="runs.runFinalSourceMode">
            <option value="processed">processed</option>
            <option value="raw">raw</option>
            <option value="translated">translated</option>
          </select>
        </label>
        <label>Display
          <select v-model="runs.runFinalDisplayMode">
            <option value="single">single</option>
            <option value="compare">compare</option>
          </select>
        </label>
      </div>
      <label class="toggle-small">
        <input type="checkbox" v-model="runs.runShowOriginalText" />
        <span>Show Original Text</span>
      </label>

      <DownloadLinks :detail="runs.selectedRunDetail" />
      <SlideList
        :run-id="runs.selectedRunId"
        :slides-mode="runs.runSlidesMode"
        :source-mode="runs.runFinalSourceMode"
        :display-mode="runs.runFinalDisplayMode"
        :show-original-text="runs.runShowOriginalText"
        :refresh-key="runRefreshKey"
        @open-image="(url, name) => $emit('open-image', url, name)"
        @set-image-mode="onSetImageMode"
      />
    </section>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { runStore as runs, loadSelectedRunDetails, setFinalSlideImageMode } from "../stores/runStore.js";
import RunCard from "../components/RunCard.vue";
import DownloadLinks from "../components/DownloadLinks.vue";
import SlideList from "../components/SlideList.vue";

const emit = defineEmits(["open-image"]);
const runRefreshKey = ref(0);

async function selectRun(id) {
  if (runs.selectedRunId === id) return;
  runs.selectedRunId = id;
  await loadSelectedRunDetails();
}

async function onSetImageMode(runId, eventId, mode) {
  await setFinalSlideImageMode(runId, eventId, mode);
  runRefreshKey.value++;
}
</script>
