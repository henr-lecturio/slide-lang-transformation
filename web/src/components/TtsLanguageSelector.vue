<template>
  <div class="settings-row">
    <label class="settings-key" for="final_slide_target_language_search">TARGET_LANGUAGE_SEARCH</label>
    <div class="settings-value">
      <input
        id="final_slide_target_language_search"
        type="search"
        placeholder="Search language..."
        autocomplete="off"
        :value="searchText"
        :disabled="disabled"
        @input="$emit('update:searchText', $event.target.value)"
      />
    </div>
  </div>
  <div class="settings-row">
    <label class="settings-key" for="final_slide_target_language">TARGET_LANGUAGE</label>
    <div class="settings-value">
      <select
        id="final_slide_target_language"
        :value="modelValue"
        :disabled="disabled"
        @change="onSelect($event.target.value)"
      >
        <option v-if="filtered.length === 0" value="">No matching languages</option>
        <option
          v-for="item in filtered"
          :key="item.tts_language_code"
          :value="item.tts_language_code"
          :data-tts-language-code="item.tts_language_code"
          :data-label="item.label"
        >{{ formatOptionLabel(item) }}</option>
      </select>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { normalizeLanguageSearch } from "../stores/configStore.js";

const props = defineProps({
  options: { type: Array, default: () => [] },
  modelValue: { type: String, default: "" },
  searchText: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "update:searchText"]);

const filtered = computed(() => {
  const query = normalizeLanguageSearch(props.searchText);
  if (!query) return props.options;
  return props.options.filter((item) => {
    const readiness = normalizeLanguageSearch(item.launch_readiness || "");
    const label = normalizeLanguageSearch(item.label || "");
    const code = normalizeLanguageSearch(item.tts_language_code || "");
    return label.includes(query) || code.includes(query) || readiness.includes(query);
  });
});

function formatOptionLabel(item) {
  return item.launch_readiness
    ? `${item.label} [${item.tts_language_code}] (${item.launch_readiness})`
    : `${item.label} [${item.tts_language_code}]`;
}

function onSelect(code) {
  emit("update:modelValue", code);
}
</script>
