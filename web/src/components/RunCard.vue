<template>
  <button type="button" class="run-card" :class="{ active }" @click="$emit('select')">
    <div class="run-card-head">
      <div class="run-card-title" :title="run.id">{{ formatRunIdLabel(run.id) }}</div>
      <span :class="['run-card-badge', 'is-' + (run.run_status || 'idle')]">{{ run.run_status || 'idle' }}</span>
    </div>
  </button>
</template>

<script setup>
import { formatRunIdLabel } from "../stores/configStore.js";

defineProps({
  run: { type: Object, required: true },
  active: { type: Boolean, default: false },
});

defineEmits(["select"]);
</script>
