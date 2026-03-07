<template>
  <div class="image-wrap" :class="wrapClass">
    <img
      v-if="src"
      :src="src"
      :alt="alt"
      :loading="loading"
      style="cursor: zoom-in"
      @click="onClick"
    />
    <img v-else :alt="alt" />
  </div>
</template>

<script setup>
const props = defineProps({
  src: { type: String, default: "" },
  alt: { type: String, default: "" },
  zoomSrc: { type: String, default: "" },
  zoomCaption: { type: String, default: "" },
  wrapClass: { type: [String, Array, Object], default: "" },
  loading: { type: String, default: undefined },
});

function onClick() {
  if (!props.src) return;
  const url = props.zoomSrc || props.src;
  const caption = props.zoomCaption || props.alt;
  if (typeof window.__openImageModal === "function") {
    window.__openImageModal(url, caption);
  }
}
</script>
