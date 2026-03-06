<template>
  <div class="lab-toolbar">
    <div class="lab-toolbar-main">
      <slot name="actions" />
    </div>
    <div class="lab-toolbar-side">
      <StatusLine :status="status" :has-selection="hasSelection" :idle-label="idleLabel" />
      <button type="button" @click="$emit('open-terminal')">Open Terminal</button>
      <button type="button" :disabled="status !== 'running'" @click="$emit('stop')">
        {{ status === 'stopping' ? 'Stopping...' : 'Stop Execution' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import StatusLine from "./StatusLine.vue";

defineProps({
  status: { type: String, default: "idle" },
  hasSelection: { type: Boolean, default: false },
  idleLabel: { type: String, default: "No image selected" },
});

defineEmits(["open-terminal", "stop"]);
</script>
