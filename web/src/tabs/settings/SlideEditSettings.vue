<template>
  <div class="settings-list">
    <SettingsRow label="FINAL_SLIDE_POSTPROCESS_MODE" field-id="final_slide_postprocess_mode">
      <select id="final_slide_postprocess_mode" v-model="f.FINAL_SLIDE_POSTPROCESS_MODE" :disabled="!f.RUN_STEP_EDIT">
        <option value="local">local</option>
        <option value="gemini">nano banana</option>
        <option value="none">none</option>
      </select>
    </SettingsRow>
    <SettingsRow label="SLIDE_EDIT_REVIEW_RETRIES" field-id="gemini_edit_review_retries"><input id="gemini_edit_review_retries" type="number" min="0" max="5" step="1" v-model="f.GEMINI_EDIT_REVIEW_RETRIES" :disabled="!f.RUN_STEP_EDIT" /></SettingsRow>
    <SettingsRow label="SLIDE_EDIT_MODEL" field-id="gemini_edit_model">
      <select id="gemini_edit_model" v-model="f.GEMINI_EDIT_MODEL" :disabled="!f.RUN_STEP_EDIT">
        <option value="gemini-3.1-flash-image-preview">gemini-3.1-flash-image-preview</option>
        <option value="gemini-3-pro-image-preview">gemini-3-pro-image-preview</option>
        <option value="gemini-2.5-flash-image">gemini-2.5-flash-image</option>
      </select>
    </SettingsRow>
    <div class="settings-row settings-row-textarea">
      <label class="settings-key" for="gemini_edit_prompt">SLIDE_EDIT_PROMPT</label>
      <div class="settings-value"><textarea id="gemini_edit_prompt" rows="10" v-model="f.GEMINI_EDIT_PROMPT" :disabled="!f.RUN_STEP_EDIT"></textarea></div>
    </div>
  </div>
</template>

<script setup>
import { configStore as store } from "../../stores/configStore.js";
import SettingsRow from "../../components/SettingsRow.vue";

const f = store.form;
</script>
