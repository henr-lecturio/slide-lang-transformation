<template>
  <div class="slides-list">
    <div v-if="!runId" class="muted"></div>
    <div v-else-if="loading" class="muted">Loading...</div>
    <div v-else-if="items.length === 0" class="muted">{{ emptyMessage }}</div>
    <article v-for="item in items" :key="item.event_id" class="slide-row">
      <div class="slide-media">
        <!-- Compare mode -->
        <template v-if="slidesMode === 'final' && displayMode === 'compare'">
          <div class="slide-compare-grid">
            <div class="slide-compare-panel">
              <div class="slide-compare-label">{{ compareImages(item).left.slideSourceLabel }} | native</div>
              <img v-if="compareImages(item).left.url" loading="lazy" :src="compareImages(item).left.url" :alt="compareImages(item).left.name || fallbackName(item)" @click="$emit('open-image', compareImages(item).left.url, compareImages(item).left.name || fallbackName(item))" />
              <div v-else class="slide-missing muted">{{ compareImages(item).left.missingReason || 'No image' }}</div>
            </div>
            <div class="slide-compare-panel">
              <div class="slide-compare-label">{{ compareImages(item).left.slideSourceLabel }} | x4</div>
              <img v-if="compareImages(item).right.url" loading="lazy" :src="compareImages(item).right.url" :alt="compareImages(item).right.name || fallbackName(item)" @click="$emit('open-image', compareImages(item).right.url, compareImages(item).right.name || fallbackName(item))" />
              <div v-else class="slide-missing muted">{{ compareImages(item).right.missingReason || 'No image' }}</div>
            </div>
          </div>
        </template>
        <!-- Single/base mode -->
        <template v-else-if="slidesMode === 'final'">
          <img v-if="singleImage(item).url" loading="lazy" :src="singleImage(item).url" :alt="singleImage(item).name || fallbackName(item)" @click="$emit('open-image', singleImage(item).url, singleImage(item).name || fallbackName(item))" />
          <div v-else class="slide-missing muted">No image</div>
        </template>
        <template v-else>
          <img v-if="item.image_url" loading="lazy" :src="item.image_url" :alt="item.image_name || fallbackName(item)" @click="$emit('open-image', item.image_url, item.image_name || fallbackName(item))" />
          <div v-else class="slide-missing muted">No image</div>
        </template>

        <!-- Image mode toggle (ROI/Full) -->
        <div v-if="slidesMode === 'final' && hasImageModeToggle(item)" class="slide-controls">
          <span class="slide-controls-label">Image:</span>
          <div class="mode-toggle">
            <button v-for="mode in [{key:'slide',label:'ROI'},{key:'full',label:'Full'}]" :key="mode.key" type="button" class="mode-toggle-btn" :class="{ active: item.image_mode === mode.key }" :disabled="!item.available_image_modes?.includes(mode.key)" @click="$emit('set-image-mode', runId, item.event_id, mode.key)">{{ mode.label }}</button>
          </div>
        </div>

        <!-- Slide details -->
        <SlideDetails v-if="slidesMode === 'final'" :facts="finalDetailsFacts(item)" />
        <SlideDetails v-else :facts="baseDetailsFacts(item)" />

        <div v-if="item.translation_note" class="slide-translation-note">{{ item.translation_note }}</div>
        <div v-if="item.consistency_note" class="slide-consistency-note">{{ item.consistency_note }}</div>
      </div>

      <!-- Text block -->
      <div v-if="slidesMode === 'final'" class="slide-text">
        <div class="slide-text-main">{{ translatedText(item) || originalText(item) || '(no text)' }}</div>
        <template v-if="showOriginalText && originalText(item)">
          <div class="slide-text-divider"></div>
          <div class="slide-text-original">{{ originalText(item) }}</div>
        </template>
      </div>
      <div v-else class="slide-text">timecode: {{ item.timecode || '' }}
transition_no: {{ item.transition_no }}
frame_id_0: {{ item.frame_id_0 }}
frame_id_1: {{ item.frame_id_1 }}</div>
    </article>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { apiGet } from "../composables/useApi.js";
import { resolveRenderedFinalImage, resolveCompareRenderedImages } from "../stores/runStore.js";

const SlideDetails = {
  props: { facts: Array },
  template: `<section class="output-info-panel slide-details-panel" :class="{ 'is-open': open }">
    <button type="button" class="output-info-toggle" :aria-expanded="open ? 'true' : 'false'" @click="open = !open">
      <span>Slide Details</span>
      <span class="step-section-chevron" aria-hidden="true"></span>
    </button>
    <div class="output-info-body" :hidden="!open">
      <div class="output-info-grid">
        <div v-for="[label, value] in facts" :key="label" class="output-info-item">
          <div class="output-info-label">{{ label }}</div>
          <div class="output-info-value">{{ value }}</div>
        </div>
      </div>
    </div>
  </section>`,
  data() { return { open: false }; },
};

const props = defineProps({
  runId: { type: String, default: "" },
  slidesMode: { type: String, default: "final" },
  sourceMode: { type: String, default: "processed" },
  displayMode: { type: String, default: "single" },
  showOriginalText: { type: Boolean, default: true },
  refreshKey: { type: Number, default: 0 },
});

defineEmits(["open-image", "set-image-mode"]);

const items = ref([]);
const loading = ref(false);

const emptyMessage = ref("");

function fallbackName(item) {
  return `event_${item.event_id}`;
}

function singleImage(item) {
  return resolveRenderedFinalImage(item, props.sourceMode);
}

function compareImages(item) {
  return resolveCompareRenderedImages(item, props.sourceMode);
}

function hasImageModeToggle(item) {
  return Array.isArray(item.available_image_modes) && item.available_image_modes.length > 1;
}

function translatedText(item) {
  return String(item.translated_text || "").trim();
}

function originalText(item) {
  return String(item.text || "").trim();
}

function finalDetailsFacts(item) {
  if (props.displayMode === "compare") {
    const compare = compareImages(item);
    return [
      ["Event", String(item.event_id)],
      ["Start", `${Number(item.slide_start).toFixed(2)}s`],
      ["End", `${Number(item.slide_end).toFixed(2)}s`],
      ["Image", item.image_mode || "-"],
      ["Final Source", item.source_mode_final || "-"],
      ["ROI Source", compare.left.slideSourceLabel],
      ["Display", "compare"],
    ];
  }
  const rendered = singleImage(item);
  return [
    ["Event", String(item.event_id)],
    ["Start", `${Number(item.slide_start).toFixed(2)}s`],
    ["End", `${Number(item.slide_end).toFixed(2)}s`],
    ["Image", item.image_mode || "-"],
    ["Final Source", item.source_mode_final || "-"],
    ["ROI Source", rendered.slideSourceLabel],
    ["Resolution", rendered.resolutionLabel],
  ];
}

function baseDetailsFacts(item) {
  return [
    ["Event", String(item.event_id)],
    ["Time", `${Number(item.time_sec).toFixed(2)}s`],
    ["Frame", String(item.event_frame)],
  ];
}

async function loadSlides() {
  if (!props.runId) {
    items.value = [];
    return;
  }
  loading.value = true;
  try {
    if (props.slidesMode === "base") {
      const data = await apiGet(`/api/runs/${encodeURIComponent(props.runId)}/base-events`);
      items.value = data.items || [];
      emptyMessage.value = "No base events available for this run.";
    } else {
      const data = await apiGet(`/api/runs/${encodeURIComponent(props.runId)}/final-slides`);
      items.value = data.items || [];
      emptyMessage.value = "No final slide text map available for this run.";
    }
  } catch {
    items.value = [];
  } finally {
    loading.value = false;
  }
}

watch(() => [props.runId, props.slidesMode, props.sourceMode, props.displayMode, props.showOriginalText, props.refreshKey], loadSlides, { immediate: true });
</script>
