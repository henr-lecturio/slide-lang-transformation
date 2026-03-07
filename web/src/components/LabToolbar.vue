<template>
  <div class="lab-toolbar">
    <div class="lab-toolbar-main">
      <slot name="actions" />
    </div>
    <div class="lab-toolbar-side">
      <StatusLine :status="status" :has-selection="hasSelection" :idle-label="idleLabel" />
      <AppButton @click="$emit('open-terminal')">Open Terminal</AppButton>
      <AppButton variant="danger" :disabled="status !== 'running'" @click="$emit('stop')">
        {{ status === 'stopping' ? 'Stopping...' : 'Stop Execution' }}
      </AppButton>
    </div>
  </div>
</template>

<script setup>
import StatusLine from "./StatusLine.vue";
import AppButton from "./AppButton.vue";

defineProps({
  status: { type: String, default: "idle" },
  hasSelection: { type: Boolean, default: false },
  idleLabel: { type: String, default: "No image selected" },
});

defineEmits(["open-terminal", "stop"]);
</script>
