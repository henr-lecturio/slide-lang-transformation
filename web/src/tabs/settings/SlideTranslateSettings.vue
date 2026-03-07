<template>
  <div class="settings-list">
    <SettingsRow label="FINAL_SLIDE_TRANSLATION_MODE" field-id="final_slide_translation_mode">
      <select id="final_slide_translation_mode" v-model="f.FINAL_SLIDE_TRANSLATION_MODE" :disabled="!f.RUN_STEP_TRANSLATE" @change="$emit('field-change')">
        <option value="none">none</option>
        <option value="gemini">nano banana</option>
        <option value="deterministic_glossary">Google OCR + Glossary</option>
      </select>
    </SettingsRow>
    <!-- Gemini subsections -->
    <div class="settings-subsection">
      <h4 class="settings-subsection-head">Step 1 — Extract</h4>
      <div class="settings-list">
        <SettingsRow label="EXTRACT_MODEL" field-id="gemini_extract_model">
          <select id="gemini_extract_model" v-model="f.GEMINI_EXTRACT_MODEL" :disabled="!f.RUN_STEP_TRANSLATE || !geminiSlideTranslate">
            <option value="gemini-3.1-pro-preview">gemini-3.1-pro-preview</option>
            <option value="gemini-2.5-pro">gemini-2.5-pro</option>
            <option value="gemini-2.5-flash">gemini-2.5-flash</option>
          </select>
        </SettingsRow>
        <div class="settings-row settings-row-textarea">
          <label class="settings-key" for="gemini_slide_extract_prompt">EXTRACT_PROMPT</label>
          <div class="settings-value"><textarea id="gemini_slide_extract_prompt" rows="5" v-model="f.GEMINI_SLIDE_EXTRACT_PROMPT" :disabled="!f.RUN_STEP_TRANSLATE || !geminiSlideTranslate"></textarea></div>
        </div>
      </div>
    </div>
    <div class="settings-subsection">
      <h4 class="settings-subsection-head">Step 2 — Translate</h4>
      <div class="settings-list">
        <div class="settings-row settings-row-textarea">
          <label class="settings-key" for="gemini_slide_translate_prompt">TRANSLATE_PROMPT</label>
          <div class="settings-value"><textarea id="gemini_slide_translate_prompt" rows="5" v-model="f.GEMINI_SLIDE_TRANSLATE_PROMPT" :disabled="!f.RUN_STEP_TRANSLATE || !geminiSlideTranslate"></textarea></div>
        </div>
      </div>
    </div>
    <div class="settings-subsection">
      <h4 class="settings-subsection-head">Step 3 — Render</h4>
      <div class="settings-list">
        <SettingsRow label="RENDER_MODEL" field-id="gemini_translate_model">
          <select id="gemini_translate_model" v-model="f.GEMINI_TRANSLATE_MODEL" :disabled="!f.RUN_STEP_TRANSLATE || !geminiSlideTranslate">
            <option value="gemini-3.1-flash-image-preview">gemini-3.1-flash-image-preview</option>
            <option value="gemini-3-pro-image-preview">gemini-3-pro-image-preview</option>
            <option value="gemini-2.5-flash-image">gemini-2.5-flash-image</option>
          </select>
        </SettingsRow>
        <div class="settings-row settings-row-textarea">
          <label class="settings-key" for="gemini_slide_render_prompt">RENDER_PROMPT</label>
          <div class="settings-value"><textarea id="gemini_slide_render_prompt" rows="5" v-model="f.GEMINI_SLIDE_RENDER_PROMPT" :disabled="!f.RUN_STEP_TRANSLATE || !geminiSlideTranslate"></textarea></div>
        </div>
      </div>
    </div>
    <!-- Deterministic Glossary -->
    <div class="settings-subsection">
      <h4 class="settings-subsection-head">Deterministic Glossary</h4>
      <div class="settings-list">
        <SettingsRow label="SLIDE_TRANSLATE_MAX_FONT_SIZE" field-id="slide_translate_max_font_size"><input id="slide_translate_max_font_size" type="number" min="8" step="1" v-model="f.SLIDE_TRANSLATE_MAX_FONT_SIZE" :disabled="!f.RUN_STEP_TRANSLATE || !deterministicSlideTranslate" /></SettingsRow>
      </div>
    </div>
    <div class="settings-row termbase-settings-row">
      <label class="settings-key" for="slide_translate_styles_json">Slide Translate Styling</label>
      <div class="settings-value">
        <StyleEditor v-model="f.SLIDE_TRANSLATE_STYLES_JSON" :disabled="!f.RUN_STEP_TRANSLATE || !deterministicSlideTranslate" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { configStore as store } from "../../stores/configStore.js";
import SettingsRow from "../../components/SettingsRow.vue";
import StyleEditor from "../../components/StyleEditor.vue";

defineEmits(["field-change"]);

const f = store.form;
const geminiSlideTranslate = computed(() => f.FINAL_SLIDE_TRANSLATION_MODE === "gemini");
const deterministicSlideTranslate = computed(() => f.FINAL_SLIDE_TRANSLATION_MODE === "deterministic_glossary");
</script>
