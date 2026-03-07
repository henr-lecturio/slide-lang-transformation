<template>
  <div class="output-info-panel" :class="[panelClass, { 'is-open': open }]">
    <button class="output-info-toggle" type="button" :disabled="disabled" :aria-expanded="open ? 'true' : 'false'" @click="$emit('update:open', !open)">
      <span>{{ title }}</span>
      <span class="step-section-chevron" aria-hidden="true"></span>
    </button>
    <div class="output-info-body" :hidden="!open">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: "" },
  open: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  panelClass: { type: [String, Array, Object], default: "" },
});

defineEmits(["update:open"]);
</script>
