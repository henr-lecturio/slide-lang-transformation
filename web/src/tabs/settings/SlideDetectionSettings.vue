<template>
  <div class="settings-list">
    <SettingsRow label="KEYFRAME_SETTLE_FRAMES" field-id="keyframe_settle_frames"><input id="keyframe_settle_frames" type="number" min="0" step="1" v-model="f.KEYFRAME_SETTLE_FRAMES" /></SettingsRow>
    <SettingsRow label="KEYFRAME_STABLE_END_GUARD_FRAMES" field-id="keyframe_stable_end_guard_frames"><input id="keyframe_stable_end_guard_frames" type="number" min="0" step="1" v-model="f.KEYFRAME_STABLE_END_GUARD_FRAMES" /></SettingsRow>
    <SettingsRow label="KEYFRAME_STABLE_LOOKAHEAD_FRAMES" field-id="keyframe_stable_lookahead_frames"><input id="keyframe_stable_lookahead_frames" type="number" min="1" step="1" v-model="f.KEYFRAME_STABLE_LOOKAHEAD_FRAMES" /></SettingsRow>
  </div>
</template>

<script setup>
import { configStore as store } from "../../stores/configStore.js";
import SettingsRow from "../../components/SettingsRow.vue";

const f = store.form;
</script>
