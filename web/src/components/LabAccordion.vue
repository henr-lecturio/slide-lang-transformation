<template>
  <details class="lab-accordion" :open="startOpen || undefined">
    <summary class="lab-accordion-header">
      <span class="lab-accordion-chevron"></span>
      <h2><slot name="title" /></h2>
    </summary>
    <section class="card lab-accordion-body">
      <slot />
    </section>
  </details>
</template>

<script setup>
defineProps({
  startOpen: { type: Boolean, default: false },
});
</script>
