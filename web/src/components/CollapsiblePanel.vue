<template>
  <div class="output-info-panel" :class="[panelClass, { 'is-open': localOpen }]">
    <button class="output-info-toggle" type="button" :disabled="disabled" :aria-expanded="localOpen ? 'true' : 'false'" @click="toggle">
      <span>{{ title }}</span>
      <span class="step-section-chevron" aria-hidden="true"></span>
    </button>
    <div class="output-info-body" :hidden="!localOpen">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from "vue";

const STORAGE_KEY = "collapsible-panel-state";

const props = defineProps({
  title: { type: String, default: "" },
  open: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  panelClass: { type: [String, Array, Object], default: "" },
  name: { type: String, default: "" },
});

const emit = defineEmits(["update:open"]);

function loadState() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; }
  catch { return {}; }
}

const localOpen = ref(props.open);

onMounted(() => {
  if (props.name) {
    const saved = loadState();
    if (props.name in saved) localOpen.value = saved[props.name];
  }
});

watch(() => props.open, (val) => { localOpen.value = val; });

function toggle() {
  localOpen.value = !localOpen.value;
  emit("update:open", localOpen.value);
  if (props.name) {
    const saved = loadState();
    saved[props.name] = localOpen.value;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
  }
}
</script>
