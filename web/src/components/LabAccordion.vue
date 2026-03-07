<template>
  <details class="lab-accordion" :open="isOpen || undefined" @toggle="onToggle">
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
import { ref, onMounted } from "vue";

const STORAGE_KEY = "lab-accordion-state";

const props = defineProps({
  name: { type: String, required: true },
  startOpen: { type: Boolean, default: false },
});

function loadState() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch { return {}; }
}

const isOpen = ref(props.startOpen);

onMounted(() => {
  const saved = loadState();
  if (props.name in saved) isOpen.value = saved[props.name];
});

function onToggle(e) {
  isOpen.value = e.target.open;
  const saved = loadState();
  saved[props.name] = e.target.open;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
}
</script>
