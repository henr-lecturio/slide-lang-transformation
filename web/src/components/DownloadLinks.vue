<template>
  <div class="summary-links row wrap">
    <span v-if="links.length === 0" class="muted">No export files available.</span>
    <a v-for="link in links" :key="link.label" class="summary-link" :href="link.url" :download="link.name">{{ link.label }}</a>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { getDownloadLinks } from "../stores/runStore.js";

const props = defineProps({
  detail: { type: Object, default: null },
  includeVideo: { type: Boolean, default: true },
  includeNonVideo: { type: Boolean, default: true },
});

const links = computed(() => getDownloadLinks(props.detail, {
  includeVideo: props.includeVideo,
  includeNonVideo: props.includeNonVideo,
}));
</script>
