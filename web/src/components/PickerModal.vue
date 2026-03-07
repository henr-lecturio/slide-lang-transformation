<template>
  <AppModal :open="open" base-class="video-picker-modal" dialog-class="video-picker-dialog" backdrop-class="video-picker-backdrop" :aria-label="title" @close="$emit('close')">
    <ModalHeader :title="title" @close="$emit('close')" />
    <div class="video-picker-list">
      <div v-if="items.length === 0" class="muted">{{ emptyText }}</div>
      <button
        v-for="item in items"
        :key="itemKey(item)"
        type="button"
        :class="['video-item', 'video-file', { selected: isSelected(item) }]"
        :disabled="isDisabled(item)"
        :title="labelFn(item)"
        @click="$emit('select', item)"
      >
        {{ labelFn(item) }}
      </button>
    </div>
  </AppModal>
</template>

<script setup>
import AppModal from "./AppModal.vue";
import ModalHeader from "./ModalHeader.vue";

defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: "Select" },
  items: { type: Array, default: () => [] },
  labelFn: { type: Function, default: (item) => String(item) },
  itemKey: { type: Function, default: (item, i) => i },
  isSelected: { type: Function, default: () => false },
  isDisabled: { type: Function, default: () => false },
  emptyText: { type: String, default: "No items available." },
});

defineEmits(["close", "select"]);
</script>
