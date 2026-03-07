<template>
  <button
    ref="btnRef"
    :type="type"
    :disabled="disabled || showingSuccess"
    :class="['app-btn', variantClass]"
    @click="onClick"
  ><slot>{{ label }}</slot></button>
</template>

<script setup>
import { ref, computed } from "vue";

const props = defineProps({
  label: { type: String, default: "" },
  type: { type: String, default: "button" },
  disabled: { type: Boolean, default: false },
  variant: { type: String, default: "" },
  successLabel: { type: String, default: "" },
});

const emit = defineEmits(["click"]);

const btnRef = ref(null);
const showingSuccess = ref(false);
let timer = null;

const variantClass = computed(() => {
  if (props.variant) return `app-btn--${props.variant}`;
  return "";
});

function onClick(e) {
  emit("click", e);
}

function flashSuccess(label) {
  const btn = btnRef.value;
  if (!btn) return;
  if (timer) clearTimeout(timer);

  const original = btn.textContent;
  btn.textContent = label || props.successLabel || "Saved";
  btn.classList.add("is-success");
  showingSuccess.value = true;

  timer = setTimeout(() => {
    btn.classList.remove("is-success");
    btn.textContent = original;
    showingSuccess.value = false;
    timer = null;
  }, 1600);
}

defineExpose({ flashSuccess, el: btnRef });
</script>
