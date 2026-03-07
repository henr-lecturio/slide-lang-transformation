<template>
  <section class="output-info-panel slide-details-panel" :class="{ 'is-open': open }">
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
  </section>
</template>

<script setup>
import { ref } from "vue";

defineProps({
  facts: { type: Array, default: () => [] },
});

const open = ref(false);
</script>
