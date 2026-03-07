<template>
  <div class="settings-list">
    <div class="settings-subhead">Speaker Filter</div>
    <SettingsRow label="SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO" field-id="speaker_filter_min_stage1_video_ratio"><input id="speaker_filter_min_stage1_video_ratio" type="number" min="0" max="1" step="0.01" v-model="f.SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO" /></SettingsRow>
    <SettingsRow label="SPEAKER_FILTER_MAX_EDGE_DENSITY" field-id="speaker_filter_max_edge_density"><input id="speaker_filter_max_edge_density" type="number" min="0" max="1" step="0.001" v-model="f.SPEAKER_FILTER_MAX_EDGE_DENSITY" /></SettingsRow>
    <SettingsRow label="SPEAKER_FILTER_MAX_LAPLACIAN_VAR" field-id="speaker_filter_max_laplacian_var"><input id="speaker_filter_max_laplacian_var" type="number" min="0" step="1" v-model="f.SPEAKER_FILTER_MAX_LAPLACIAN_VAR" /></SettingsRow>
    <SettingsRow label="SPEAKER_FILTER_MAX_DURATION_SEC" field-id="speaker_filter_max_duration_sec"><input id="speaker_filter_max_duration_sec" type="number" min="0" step="0.1" v-model="f.SPEAKER_FILTER_MAX_DURATION_SEC" /></SettingsRow>
    <div class="settings-subhead">Final Source Auto</div>
    <SettingsRow label="FINAL_SOURCE_MODE_AUTO" field-id="final_source_mode_auto">
      <select id="final_source_mode_auto" v-model="f.FINAL_SOURCE_MODE_AUTO">
        <option value="auto">auto</option>
        <option value="off">off</option>
      </select>
    </SettingsRow>
    <SettingsRow label="FULLSLIDE_SAMPLE_FRAMES" field-id="fullslide_sample_frames"><input id="fullslide_sample_frames" type="number" min="1" step="1" v-model="f.FULLSLIDE_SAMPLE_FRAMES" /></SettingsRow>
    <SettingsRow label="FULLSLIDE_BORDER_STRIP_PX" field-id="fullslide_border_strip_px"><input id="fullslide_border_strip_px" type="number" min="2" step="1" v-model="f.FULLSLIDE_BORDER_STRIP_PX" /></SettingsRow>
    <SettingsRow label="FULLSLIDE_MIN_MATCHED_SIDES" field-id="fullslide_min_matched_sides"><input id="fullslide_min_matched_sides" type="number" min="1" max="4" step="1" v-model="f.FULLSLIDE_MIN_MATCHED_SIDES" /></SettingsRow>
    <SettingsRow label="FULLSLIDE_BORDER_DIFF_THRESHOLD" field-id="fullslide_border_diff_threshold"><input id="fullslide_border_diff_threshold" type="number" min="0" step="0.1" v-model="f.FULLSLIDE_BORDER_DIFF_THRESHOLD" /></SettingsRow>
    <SettingsRow label="FULLSLIDE_PERSON_BOX_AREA_RATIO" field-id="fullslide_person_box_area_ratio"><input id="fullslide_person_box_area_ratio" type="number" min="0" max="1" step="0.01" v-model="f.FULLSLIDE_PERSON_BOX_AREA_RATIO" /></SettingsRow>
    <SettingsRow label="FULLSLIDE_PERSON_OUTSIDE_RATIO" field-id="fullslide_person_outside_ratio"><input id="fullslide_person_outside_ratio" type="number" min="0" max="1" step="0.01" v-model="f.FULLSLIDE_PERSON_OUTSIDE_RATIO" /></SettingsRow>
  </div>
</template>

<script setup>
import { configStore as store } from "../../stores/configStore.js";
import SettingsRow from "../../components/SettingsRow.vue";

const f = store.form;
</script>
