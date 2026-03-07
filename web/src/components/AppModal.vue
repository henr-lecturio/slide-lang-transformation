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
import { onMounted, onUnmounted } from "vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  ariaLabel: { type: String, default: "" },
  baseClass: { type: String, default: "status-modal" },
  dialogClass: { type: String, default: "status-modal-dialog" },
  backdropClass: { type: String, default: "status-modal-backdrop" },
});

const emit = defineEmits(["close"]);

function onKeydown(e) {
  if (e.key === "Escape" && props.open) {
    emit("close");
  }
}

onMounted(() => document.addEventListener("keydown", onKeydown));
onUnmounted(() => document.removeEventListener("keydown", onKeydown));
</script>
