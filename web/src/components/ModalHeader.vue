<template>
  <div class="modal-head" :class="headClass">
    <h3>{{ title }}</h3>
    <div v-if="$slots.actions" class="lab-settings-head-actions">
      <slot name="actions" />
      <button class="modal-close" type="button" :aria-label="`Close ${title}`" @click="$emit('close')">&times;</button>
    </div>
    <button v-else class="modal-close" type="button" :aria-label="`Close ${title}`" @click="$emit('close')">&times;</button>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: "" },
  headClass: { type: [String, Array, Object], default: "" },
});

defineEmits(["close"]);
</script>
