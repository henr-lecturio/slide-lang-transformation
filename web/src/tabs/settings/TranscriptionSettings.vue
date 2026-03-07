<template>
  <div class="settings-list">
    <SettingsRow label="TRANSCRIPTION_MODEL" field-id="transcription_provider">
      <select id="transcription_provider" v-model="f.TRANSCRIPTION_PROVIDER" @change="$emit('field-change')">
        <option value="whisper">whisper</option>
        <option value="google_chirp_3">google_chirp_3</option>
      </select>
    </SettingsRow>
    <div class="settings-subhead">Whisper</div>
    <SettingsRow label="WHISPER_MODEL" field-id="whisper_model"><input id="whisper_model" type="text" v-model="f.WHISPER_MODEL" :disabled="googleTranscription" /></SettingsRow>
    <SettingsRow label="WHISPER_DEVICE" field-id="whisper_device"><input id="whisper_device" type="text" v-model="f.WHISPER_DEVICE" :disabled="googleTranscription" /></SettingsRow>
    <SettingsRow label="WHISPER_COMPUTE_TYPE" field-id="whisper_compute_type"><input id="whisper_compute_type" type="text" v-model="f.WHISPER_COMPUTE_TYPE" :disabled="googleTranscription" /></SettingsRow>
    <SettingsRow label="WHISPER_LANGUAGE" field-id="whisper_language"><input id="whisper_language" type="text" v-model="f.WHISPER_LANGUAGE" :disabled="googleTranscription" /></SettingsRow>
    <div class="settings-subhead">Google Speech</div>
    <SettingsRow label="GOOGLE_SPEECH_LOCATION" field-id="google_speech_location"><input id="google_speech_location" type="text" v-model="f.GOOGLE_SPEECH_LOCATION" :disabled="!googleTranscription" /></SettingsRow>
    <SettingsRow label="GOOGLE_SPEECH_MODEL" field-id="google_speech_model"><input id="google_speech_model" type="text" v-model="f.GOOGLE_SPEECH_MODEL" :disabled="!googleTranscription" /></SettingsRow>
    <SettingsRow label="GOOGLE_SPEECH_CHUNK_SEC" field-id="google_speech_chunk_sec"><input id="google_speech_chunk_sec" type="number" min="1" step="1" v-model="f.GOOGLE_SPEECH_CHUNK_SEC" :disabled="!googleTranscription" /></SettingsRow>
    <SettingsRow label="GOOGLE_SPEECH_CHUNK_OVERLAP_SEC" field-id="google_speech_chunk_overlap_sec"><input id="google_speech_chunk_overlap_sec" type="number" min="0" step="0.05" v-model="f.GOOGLE_SPEECH_CHUNK_OVERLAP_SEC" :disabled="!googleTranscription" /></SettingsRow>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { configStore as store } from "../../stores/configStore.js";
import SettingsRow from "../../components/SettingsRow.vue";

defineEmits(["field-change"]);

const f = store.form;
const googleTranscription = computed(() => f.TRANSCRIPTION_PROVIDER === "google_chirp_3");
</script>
