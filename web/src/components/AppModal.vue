<template>
  <Teleport to="body">
    <div :class="[baseClass, { open: open }]" :aria-hidden="open ? 'false' : 'true'">
      <div :class="backdropClass" @click="$emit('close')"></div>
      <div :class="dialogClass" role="dialog" aria-modal="true" :aria-label="ariaLabel">
        <slot />
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from "vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  ariaLabel: { type: String, default: "" },
  variant: { type: String, default: "status" },
});

const emit = defineEmits(["close"]);

const baseClass = computed(() =>
  props.variant === "picker" ? "video-picker-modal" : "status-modal"
);

const backdropClass = computed(() =>
  props.variant === "picker" ? "video-picker-backdrop" : "status-modal-backdrop"
);

const dialogClass = computed(() =>
  props.variant === "picker" ? "video-picker-dialog" : "status-modal-dialog"
);

function onKeydown(e) {
  if (e.key === "Escape" && props.open) {
    emit("close");
  }
}

onMounted(() => document.addEventListener("keydown", onKeydown));
onUnmounted(() => document.removeEventListener("keydown", onKeydown));
</script>
