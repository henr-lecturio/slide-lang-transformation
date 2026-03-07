<template>
  <div class="settings-list">
    <SettingsRow label="VIDEO_EXPORT_MIN_SLIDE_SEC" field-id="video_export_min_slide_sec"><input id="video_export_min_slide_sec" type="number" min="0.1" step="0.1" v-model="f.VIDEO_EXPORT_MIN_SLIDE_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_TAIL_PAD_SEC" field-id="video_export_tail_pad_sec"><input id="video_export_tail_pad_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_TAIL_PAD_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_INTRO_WHITE_SEC" field-id="video_export_intro_white_sec"><input id="video_export_intro_white_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_INTRO_WHITE_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_INTRO_FADE_SEC" field-id="video_export_intro_fade_sec"><input id="video_export_intro_fade_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_INTRO_FADE_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_THUMBNAIL_DURATION_SEC" field-id="video_export_thumbnail_duration_sec"><input id="video_export_thumbnail_duration_sec" type="number" min="0.04" step="0.05" v-model="f.VIDEO_EXPORT_THUMBNAIL_DURATION_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_THUMBNAIL_FADE_SEC" field-id="video_export_thumbnail_fade_sec"><input id="video_export_thumbnail_fade_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_THUMBNAIL_FADE_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_THUMBNAIL_TEXT_LEADIN_SEC" field-id="video_export_thumbnail_text_leadin_sec"><input id="video_export_thumbnail_text_leadin_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_THUMBNAIL_TEXT_LEADIN_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_INTRO_COLOR" field-id="video_export_intro_color"><input id="video_export_intro_color" type="text" v-model="f.VIDEO_EXPORT_INTRO_COLOR" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_OUTRO_HOLD_SEC" field-id="video_export_outro_hold_sec"><input id="video_export_outro_hold_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_OUTRO_HOLD_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_OUTRO_FADE_SEC" field-id="video_export_outro_fade_sec"><input id="video_export_outro_fade_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_OUTRO_FADE_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_OUTRO_FADE_COLOR" field-id="video_export_outro_fade_color"><input id="video_export_outro_fade_color" type="text" v-model="f.VIDEO_EXPORT_OUTRO_FADE_COLOR" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_OUTRO_BLACK_SEC" field-id="video_export_outro_black_sec"><input id="video_export_outro_black_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_OUTRO_BLACK_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_WIDTH" field-id="video_export_width"><input id="video_export_width" type="number" min="2" step="2" v-model="f.VIDEO_EXPORT_WIDTH" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_HEIGHT" field-id="video_export_height"><input id="video_export_height" type="number" min="2" step="2" v-model="f.VIDEO_EXPORT_HEIGHT" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_FPS" field-id="video_export_fps"><input id="video_export_fps" type="number" min="1" step="1" v-model="f.VIDEO_EXPORT_FPS" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
    <SettingsRow label="VIDEO_EXPORT_BG_COLOR" field-id="video_export_bg_color"><input id="video_export_bg_color" type="text" v-model="f.VIDEO_EXPORT_BG_COLOR" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
  </div>
</template>

<script setup>
import { configStore as store } from "../../stores/configStore.js";
import SettingsRow from "../../components/SettingsRow.vue";

const f = store.form;
</script>
