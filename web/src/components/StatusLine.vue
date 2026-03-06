<template>
  <div :class="['export-lab-status-line', 'lab-toolbar-status', meta.lineClass]">
    <div class="export-lab-status-chip">
      <span :class="meta.iconClass ? `step-icon ${meta.iconClass}` : 'step-icon'" aria-hidden="true"></span>
      <span class="export-lab-status-label">{{ meta.label }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  status: { type: String, default: "idle" },
  hasSelection: { type: Boolean, default: false },
  idleLabel: { type: String, default: "No image selected" },
});

const meta = computed(() => {
  switch (props.status) {
    case "running":
      return { label: "Running", iconClass: "is-running", lineClass: "is-running" };
    case "stopping":
      return { label: "Stopping", iconClass: "is-running", lineClass: "is-running" };
    case "done":
      return { label: "Done", iconClass: "is-done", lineClass: "is-done" };
    case "error":
      return { label: "Error", iconClass: "is-error", lineClass: "is-error" };
    case "stopped":
      return { label: "Stopped", iconClass: "is-stopped", lineClass: "is-stopped" };
  }
  if (!props.hasSelection) {
    return { label: props.idleLabel, iconClass: "", lineClass: "is-idle" };
  }
  return { label: "Ready", iconClass: "", lineClass: "is-ready" };
});
</script>
