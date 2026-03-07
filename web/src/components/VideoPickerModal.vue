<template>
  <AppModal :open="open" base-class="video-picker-modal" dialog-class="video-picker-dialog" backdrop-class="video-picker-backdrop" aria-label="Video picker" @close="$emit('close')">
    <ModalHeader title="Select Video" @close="$emit('close')" />
    <div class="video-picker-list">
      <div v-if="items.length === 0" class="muted">No videos found under videos/.</div>
      <template v-for="item in items" :key="item.path">
        <div v-if="item.type === 'dir'" class="video-item video-dir" :style="{ paddingLeft: item.depth * 18 + 'px' }">
          [dir] {{ item.path }}
        </div>
        <button
          v-else
          type="button"
          class="video-item video-file"
          :class="{ selected: item.path === selectedPath }"
          :style="{ paddingLeft: (item.depth * 18 + 8) + 'px' }"
          @click="$emit('select', item.path)"
        >{{ item.path }}</button>
      </template>
    </div>
  </AppModal>
</template>

<script setup>
import AppModal from "./AppModal.vue";
import ModalHeader from "./ModalHeader.vue";

defineProps({
  open: { type: Boolean, default: false },
  items: { type: Array, default: () => [] },
  selectedPath: { type: String, default: "" },
});

defineEmits(["close", "select"]);
</script>
