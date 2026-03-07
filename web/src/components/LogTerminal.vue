<template>
  <AppModal :open="open" :aria-label="title" @close="$emit('close')">
    <div class="modal-head">
      <h3>{{ title }}</h3>
      <button class="modal-close" type="button" :aria-label="`Close ${title}`" @click="$emit('close')">&times;</button>
    </div>
    <div class="status-modal-body">
      <pre ref="logPre" class="log log-status status-modal-log">{{ logText }}</pre>
    </div>
  </AppModal>
</template>

<script setup>
import { ref, computed, watch, nextTick } from "vue";
import AppModal from "./AppModal.vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: "Terminal" },
  logs: { type: Array, default: () => [] },
});

defineEmits(["close"]);

const logPre = ref(null);

const logText = computed(() => props.logs.join("\n"));

watch(logText, async () => {
  await nextTick();
  if (logPre.value) {
    logPre.value.scrollTop = logPre.value.scrollHeight;
  }
});
</script>
