<template>
  <Teleport to="body">
    <div class="image-modal" :class="{ open }" :aria-hidden="open ? 'false' : 'true'">
      <div class="image-modal-backdrop" @click="$emit('close')"></div>
      <div class="image-modal-dialog" role="dialog" aria-modal="true" aria-label="Image preview">
        <button class="image-modal-close" type="button" aria-label="Close preview" @click="$emit('close')">×</button>
        <div class="image-modal-viewport" @wheel.prevent="onWheel">
          <img
            v-if="imgSrc"
            :src="imgSrc"
            alt="Image preview"
            :style="imgStyle"
          />
        </div>
        <div class="image-modal-caption">{{ caption }}</div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  src: { type: String, default: "" },
  caption: { type: String, default: "" },
});

const emit = defineEmits(["close"]);

const MIN_SCALE = 1;
const MAX_SCALE = 6;
const ZOOM_FACTOR = 1.18;

const scale = ref(MIN_SCALE);
const originX = ref(50);
const originY = ref(50);

const imgSrc = computed(() => {
  if (!props.src) return "";
  const sep = props.src.includes("?") ? "&" : "?";
  return `${props.src}${sep}v=${Date.now()}`;
});

const imgStyle = computed(() => ({
  transformOrigin: `${originX.value.toFixed(2)}% ${originY.value.toFixed(2)}%`,
  transform: `scale(${scale.value.toFixed(3)})`,
}));

function resetZoom() {
  scale.value = MIN_SCALE;
  originX.value = 50;
  originY.value = 50;
}

watch(() => props.open, (isOpen) => {
  if (isOpen) resetZoom();
});

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function onWheel(event) {
  if (!props.open || !props.src) return;
  const img = event.currentTarget.querySelector("img");
  if (!img) return;
  const bounds = img.getBoundingClientRect();
  if (bounds.width > 0 && bounds.height > 0) {
    originX.value = clamp(((event.clientX - bounds.left) / bounds.width) * 100, 0, 100);
    originY.value = clamp(((event.clientY - bounds.top) / bounds.height) * 100, 0, 100);
  }
  if (event.deltaY < 0) {
    scale.value = clamp(scale.value * ZOOM_FACTOR, MIN_SCALE, MAX_SCALE);
  } else if (event.deltaY > 0) {
    scale.value = clamp(scale.value / ZOOM_FACTOR, MIN_SCALE, MAX_SCALE);
  }
  if (Math.abs(scale.value - MIN_SCALE) < 0.001) {
    scale.value = MIN_SCALE;
  }
}

function onKeydown(e) {
  if (e.key === "Escape" && props.open) {
    emit("close");
  }
}

onMounted(() => document.addEventListener("keydown", onKeydown));
onUnmounted(() => document.removeEventListener("keydown", onKeydown));
</script>
