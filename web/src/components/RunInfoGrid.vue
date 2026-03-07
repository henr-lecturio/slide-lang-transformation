<template>
  <div class="output-info-grid">
    <div v-if="!detail" class="muted">No run details available.</div>
    <template v-else>
      <div v-for="[label, value] in facts" :key="label" class="output-info-item">
        <div class="output-info-label">{{ label }}</div>
        <div class="output-info-value">{{ value }}</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { formatRunIdLabel, formatUsd } from "../stores/configStore.js";

const props = defineProps({
  detail: { type: Object, default: null },
});

const facts = computed(() => {
  const d = props.detail;
  if (!d) return [];
  return [
    ["Run", formatRunIdLabel(d.id)],
    ["Run Status", d.run_status || "-"],
    ["Available", d.highest_available_label || "no output yet"],
    ["Upscale Mode", d.upscale_mode_used || "-"],
    ["Upscale Cost", formatUsd(d.upscale_estimated_cost_usd)],
    ["Base Events", String(d.event_count ?? 0)],
    ["Final Events", String(d.final_event_count ?? 0)],
    ["Final Slide Images", String(d.final_slide_images ?? 0)],
    ["Translated Slide Images", String(d.translated_slide_images ?? 0)],
    ["Upscaled Slide Images", String(d.upscaled_slide_images ?? 0)],
    ["Translated x4 Slides", String(d.translated_upscaled_slide_images ?? 0)],
    ["Translated Text Events", String(d.translated_text_events ?? 0)],
    ["TTS Segments", String(d.tts_segments ?? 0)],
  ];
});
</script>
