<template>
  <AppModal :open="open" :aria-label="title" @close="$emit('close')">
    <ModalHeader :title="title" @close="$emit('close')" />
    <div class="status-modal-body">
      <pre ref="logPre" class="log log-status status-modal-log">{{ logText }}</pre>
    </div>
  </AppModal>
</template>

<script setup>
import { ref, computed, watch, nextTick } from "vue";
import AppModal from "./AppModal.vue";
import ModalHeader from "./ModalHeader.vue";

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
