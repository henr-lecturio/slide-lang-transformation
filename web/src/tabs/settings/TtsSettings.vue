<template>
  <div class="settings-list">
    <SettingsRow label="TTS_OUTPUT_LANGUAGE_CODE" field-id="google_tts_language_code">
      <input id="google_tts_language_code" type="text" readonly :value="f.GOOGLE_TTS_LANGUAGE_CODE" />
      <div class="tts-language-hint muted" :class="ttsHintClass" aria-live="polite">{{ ttsHintText }}</div>
    </SettingsRow>
    <SettingsRow label="TTS_MODEL" field-id="gemini_tts_model">
      <select id="gemini_tts_model" v-model="f.GEMINI_TTS_MODEL" :disabled="!f.RUN_STEP_TTS">
        <option value="gemini-2.5-flash-tts">gemini-2.5-flash-tts</option>
        <option value="gemini-2.5-pro-tts">gemini-2.5-pro-tts</option>
      </select>
    </SettingsRow>
    <SettingsRow label="GEMINI_TTS_VOICE" field-id="gemini_tts_voice"><input id="gemini_tts_voice" type="text" v-model="f.GEMINI_TTS_VOICE" :disabled="!f.RUN_STEP_TTS" /></SettingsRow>
    <SettingsRow label="GEMINI_TTS_SPEAKING_RATE" field-id="gemini_tts_speaking_rate"><input id="gemini_tts_speaking_rate" type="number" min="0.25" max="4.0" step="0.05" v-model="f.GEMINI_TTS_SPEAKING_RATE" :disabled="!f.RUN_STEP_TTS" /></SettingsRow>
    <div class="settings-row settings-row-textarea">
      <label class="settings-key" for="gemini_tts_prompt">TTS_PROMPT</label>
      <div class="settings-value"><textarea id="gemini_tts_prompt" rows="8" v-model="f.GEMINI_TTS_PROMPT" :disabled="!f.RUN_STEP_TTS"></textarea></div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { configStore as store, findTtsLanguageOptionByCode } from "../../stores/configStore.js";
import SettingsRow from "../../components/SettingsRow.vue";

const f = store.form;

const selectedTtsOption = computed(() => findTtsLanguageOptionByCode(f.GOOGLE_TTS_LANGUAGE_CODE));
const ttsHintText = computed(() => {
  if (!f.RUN_STEP_TTS) return "";
  const selected = selectedTtsOption.value;
  if (!selected) return "Select a supported Gemini TTS language from the catalog.";
  if (!f.RUN_STEP_TEXT_TRANSLATE) {
    return `TTS will use ${selected.label} [${selected.tts_language_code}] for the source mapped text because Transcript Translate is disabled.`;
  }
  const readiness = selected.launch_readiness ? ` | ${selected.launch_readiness}` : "";
  return `Selected Gemini TTS language: ${selected.label} | ${selected.tts_language_code}${readiness}`;
});
const ttsHintClass = computed(() => {
  if (!f.RUN_STEP_TTS) return "is-idle";
  if (!selectedTtsOption.value) return "is-warning";
  if (!f.RUN_STEP_TEXT_TRANSLATE) return "is-note";
  return "is-ok";
});
</script>
