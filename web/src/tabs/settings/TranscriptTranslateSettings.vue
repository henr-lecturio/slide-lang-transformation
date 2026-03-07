<template>
  <div class="settings-list">
    <SettingsRow label="GOOGLE_TRANSLATE_LOCATION" field-id="google_translate_location"><input id="google_translate_location" type="text" v-model="f.GOOGLE_TRANSLATE_LOCATION" :disabled="!cloudTranslateConfigEnabled" /></SettingsRow>
    <SettingsRow label="TRANSCRIPT_TRANSLATE_MODEL" field-id="gemini_text_translate_model">
      <select id="gemini_text_translate_model" v-model="f.TRANSCRIPT_TRANSLATE_MODEL" :disabled="!f.RUN_STEP_TEXT_TRANSLATE">
        <option value="gemini-2.5-pro">gemini-2.5-pro</option>
        <option value="general/translation-llm">general/translation-llm</option>
      </select>
    </SettingsRow>
    <SettingsRow label="SOURCE_LANG_CODE" field-id="google_translate_source_language_code"><input id="google_translate_source_language_code" type="text" placeholder="Optional, e.g. en" v-model="f.GOOGLE_TRANSLATE_SOURCE_LANGUAGE_CODE" :disabled="!sourceLanguageConfigEnabled" /></SettingsRow>
    <div class="settings-row settings-row-textarea">
      <label class="settings-key" for="gemini_text_translate_prompt">TRANSCRIPT_TRANSLATE_PROMPT</label>
      <div class="settings-value"><textarea id="gemini_text_translate_prompt" rows="8" v-model="f.GEMINI_TEXT_TRANSLATE_PROMPT" :disabled="!f.RUN_STEP_TEXT_TRANSLATE"></textarea></div>
    </div>
    <div class="settings-row termbase-settings-row">
      <label class="settings-key" for="translation_termbase_csv">TRANSLATION_TERMBASE_CSV</label>
      <div class="settings-value">
        <TermbaseEditor v-model="f.TRANSLATION_TERMBASE_CSV" :language-options="store.ttsLanguageOptions" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { configStore as store } from "../../stores/configStore.js";
import SettingsRow from "../../components/SettingsRow.vue";
import TermbaseEditor from "../../components/TermbaseEditor.vue";

const f = store.form;

const textTranslateUsesGeminiApi = computed(() => String(f.TRANSCRIPT_TRANSLATE_MODEL || "").trim().toLowerCase().startsWith("gemini-"));
const deterministicSlideTranslate = computed(() => f.FINAL_SLIDE_TRANSLATION_MODE === "deterministic_glossary");
const cloudTranslateConfigEnabled = computed(() =>
  (f.RUN_STEP_TEXT_TRANSLATE && !textTranslateUsesGeminiApi.value) || (f.RUN_STEP_TRANSLATE && deterministicSlideTranslate.value));
const sourceLanguageConfigEnabled = computed(() => f.RUN_STEP_TEXT_TRANSLATE || (f.RUN_STEP_TRANSLATE && deterministicSlideTranslate.value));
</script>
