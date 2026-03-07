<template>
  <div class="settings-row">
    <label class="settings-key" :for="fieldId" :title="label">{{ label }}</label>
    <div class="settings-value"><slot /></div>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, default: "" },
  fieldId: { type: String, default: undefined },
});
</script>
