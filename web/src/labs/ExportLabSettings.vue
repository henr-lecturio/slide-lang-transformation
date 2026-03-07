<template>
  <AppModal :open="open" base-class="video-picker-modal" dialog-class="video-picker-dialog lab-settings-dialog" backdrop-class="video-picker-backdrop" aria-label="Export Lab test settings" @close="$emit('close')">
      <ModalHeader title="Export Lab Test Settings" head-class="lab-settings-head" @close="$emit('close')">
        <template #actions>
          <button type="button" @click="reset">Reset from Settings</button>
          <button type="button" @click="save">Save Test Settings</button>
        </template>
      </ModalHeader>
      <div class="status-modal-body lab-settings-body">
        <div class="muted">These values apply only to <strong>Export Lab</strong> tests and never modify the main settings.</div>
        <div class="step-sections lab-step-sections">

          <section class="step-section is-forced" :class="{ 'is-open': sections.timing }">
            <div class="step-section-head">
              <div class="step-section-title-wrap">
                <div class="step-section-heading">
                  <label class="step-switch is-static step-switch-icononly"><input type="checkbox" checked disabled aria-label="Export timing test settings" /></label>
                  <h3>Timing</h3>
                  <button type="button" class="step-section-toggle export-lab-step-section-toggle" :aria-expanded="sections.timing ? 'true' : 'false'" @click="sections.timing = !sections.timing">
                    <span class="step-section-chevron" aria-hidden="true"></span>
                  </button>
                </div>
                <div class="step-section-subtitle muted">Isolated timing values for <strong>Export Lab</strong> video export tests.</div>
              </div>
            </div>
            <div class="step-section-body" :hidden="!sections.timing">
              <div class="settings-list">
                <SettingsRow v-for="f in timingFields" :key="f.key" :label="f.label" :field-id="'el_' + f.key">
                  <input v-if="f.type === 'number'" :id="'el_' + f.key" type="number" :step="f.step" :min="f.min" v-model.number="form[f.key]" />
                  <input v-else :id="'el_' + f.key" type="text" v-model="form[f.key]" />
                </SettingsRow>
              </div>
            </div>
          </section>

          <section class="step-section is-forced" :class="{ 'is-open': sections.introOutro }">
            <div class="step-section-head">
              <div class="step-section-title-wrap">
                <div class="step-section-heading">
                  <label class="step-switch is-static step-switch-icononly"><input type="checkbox" checked disabled aria-label="Export intro outro test settings" /></label>
                  <h3>Intro / Outro</h3>
                  <button type="button" class="step-section-toggle export-lab-step-section-toggle" :aria-expanded="sections.introOutro ? 'true' : 'false'" @click="sections.introOutro = !sections.introOutro">
                    <span class="step-section-chevron" aria-hidden="true"></span>
                  </button>
                </div>
                <div class="step-section-subtitle muted">Isolated intro and outro values for <strong>Export Lab</strong>.</div>
              </div>
            </div>
            <div class="step-section-body" :hidden="!sections.introOutro">
              <div class="settings-list">
                <SettingsRow v-for="f in introOutroFields" :key="f.key" :label="f.label" :field-id="'el_' + f.key">
                  <input v-if="f.type === 'number'" :id="'el_' + f.key" type="number" :step="f.step" :min="f.min" v-model.number="form[f.key]" />
                  <input v-else :id="'el_' + f.key" type="text" v-model="form[f.key]" />
                </SettingsRow>
              </div>
            </div>
          </section>

          <section class="step-section is-forced" :class="{ 'is-open': sections.outputFormat }">
            <div class="step-section-head">
              <div class="step-section-title-wrap">
                <div class="step-section-heading">
                  <label class="step-switch is-static step-switch-icononly"><input type="checkbox" checked disabled aria-label="Export output format test settings" /></label>
                  <h3>Output Format</h3>
                  <button type="button" class="step-section-toggle export-lab-step-section-toggle" :aria-expanded="sections.outputFormat ? 'true' : 'false'" @click="sections.outputFormat = !sections.outputFormat">
                    <span class="step-section-chevron" aria-hidden="true"></span>
                  </button>
                </div>
                <div class="step-section-subtitle muted">Isolated render format values for <strong>Export Lab</strong>.</div>
              </div>
            </div>
            <div class="step-section-body" :hidden="!sections.outputFormat">
              <div class="settings-list">
                <SettingsRow v-for="f in outputFormatFields" :key="f.key" :label="f.label" :field-id="'el_' + f.key">
                  <input v-if="f.type === 'number'" :id="'el_' + f.key" type="number" :step="f.step" :min="f.min" v-model.number="form[f.key]" />
                  <input v-else :id="'el_' + f.key" type="text" v-model="form[f.key]" />
                </SettingsRow>
              </div>
            </div>
          </section>

        </div>
      </div>
  </AppModal>
</template>

<script setup>
import { reactive, watch } from "vue";
import AppModal from "../components/AppModal.vue";
import ModalHeader from "../components/ModalHeader.vue";
import SettingsRow from "../components/SettingsRow.vue";

const STORAGE_KEY = "slide-transform-export-lab-test-settings";

const props = defineProps({
  open: { type: Boolean, default: false },
});

const emit = defineEmits(["close", "save"]);

const sections = reactive({ timing: false, introOutro: false, outputFormat: false });

const timingFields = [
  { key: "video_export_min_slide_sec", label: "VIDEO_EXPORT_MIN_SLIDE_SEC", type: "number", step: "0.1", min: "0" },
  { key: "video_export_tail_pad_sec", label: "VIDEO_EXPORT_TAIL_PAD_SEC", type: "number", step: "0.1", min: "0" },
  { key: "video_export_thumbnail_duration_sec", label: "VIDEO_EXPORT_THUMBNAIL_DURATION_SEC", type: "number", step: "0.1", min: "0.04" },
  { key: "video_export_thumbnail_fade_sec", label: "VIDEO_EXPORT_THUMBNAIL_FADE_SEC", type: "number", step: "0.1", min: "0" },
  { key: "video_export_thumbnail_text_leadin_sec", label: "VIDEO_EXPORT_THUMBNAIL_TEXT_LEADIN_SEC", type: "number", step: "0.1", min: "0" },
];

const introOutroFields = [
  { key: "video_export_intro_white_sec", label: "VIDEO_EXPORT_INTRO_WHITE_SEC", type: "number", step: "0.1", min: "0" },
  { key: "video_export_intro_fade_sec", label: "VIDEO_EXPORT_INTRO_FADE_SEC", type: "number", step: "0.1", min: "0" },
  { key: "video_export_intro_color", label: "VIDEO_EXPORT_INTRO_COLOR", type: "text" },
  { key: "video_export_outro_hold_sec", label: "VIDEO_EXPORT_OUTRO_HOLD_SEC", type: "number", step: "0.1", min: "0" },
  { key: "video_export_outro_fade_sec", label: "VIDEO_EXPORT_OUTRO_FADE_SEC", type: "number", step: "0.1", min: "0" },
  { key: "video_export_outro_fade_color", label: "VIDEO_EXPORT_OUTRO_FADE_COLOR", type: "text" },
  { key: "video_export_outro_black_sec", label: "VIDEO_EXPORT_OUTRO_BLACK_SEC", type: "number", step: "0.1", min: "0" },
];

const outputFormatFields = [
  { key: "video_export_width", label: "VIDEO_EXPORT_WIDTH", type: "number", step: "1", min: "1" },
  { key: "video_export_height", label: "VIDEO_EXPORT_HEIGHT", type: "number", step: "1", min: "1" },
  { key: "video_export_fps", label: "VIDEO_EXPORT_FPS", type: "number", step: "1", min: "1" },
  { key: "video_export_bg_color", label: "VIDEO_EXPORT_BG_COLOR", type: "text" },
];

const DEFAULTS = {
  video_export_min_slide_sec: 1.2,
  video_export_tail_pad_sec: 0.35,
  video_export_thumbnail_duration_sec: 2.0,
  video_export_thumbnail_fade_sec: 0.3,
  video_export_thumbnail_text_leadin_sec: 1.0,
  video_export_intro_white_sec: 1.0,
  video_export_intro_fade_sec: 0.4,
  video_export_intro_color: "white",
  video_export_outro_hold_sec: 1.5,
  video_export_outro_fade_sec: 1.5,
  video_export_outro_fade_color: "black",
  video_export_outro_black_sec: 2.0,
  video_export_width: 1920,
  video_export_height: 1080,
  video_export_fps: 30,
  video_export_bg_color: "white",
};

function readFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function getMainSettingsDefaults() {
  const el = (id) => document.getElementById(id);
  return {
    video_export_min_slide_sec: Number(el("video_export_min_slide_sec")?.value || DEFAULTS.video_export_min_slide_sec),
    video_export_tail_pad_sec: Number(el("video_export_tail_pad_sec")?.value || DEFAULTS.video_export_tail_pad_sec),
    video_export_thumbnail_duration_sec: Number(el("video_export_thumbnail_duration_sec")?.value || DEFAULTS.video_export_thumbnail_duration_sec),
    video_export_thumbnail_fade_sec: Number(el("video_export_thumbnail_fade_sec")?.value || DEFAULTS.video_export_thumbnail_fade_sec),
    video_export_thumbnail_text_leadin_sec: Number(el("video_export_thumbnail_text_leadin_sec")?.value || DEFAULTS.video_export_thumbnail_text_leadin_sec),
    video_export_intro_white_sec: Number(el("video_export_intro_white_sec")?.value || DEFAULTS.video_export_intro_white_sec),
    video_export_intro_fade_sec: Number(el("video_export_intro_fade_sec")?.value || DEFAULTS.video_export_intro_fade_sec),
    video_export_intro_color: String(el("video_export_intro_color")?.value || DEFAULTS.video_export_intro_color).trim(),
    video_export_outro_hold_sec: Number(el("video_export_outro_hold_sec")?.value || DEFAULTS.video_export_outro_hold_sec),
    video_export_outro_fade_sec: Number(el("video_export_outro_fade_sec")?.value || DEFAULTS.video_export_outro_fade_sec),
    video_export_outro_fade_color: String(el("video_export_outro_fade_color")?.value || DEFAULTS.video_export_outro_fade_color).trim(),
    video_export_outro_black_sec: Number(el("video_export_outro_black_sec")?.value || DEFAULTS.video_export_outro_black_sec),
    video_export_width: Number(el("video_export_width")?.value || DEFAULTS.video_export_width),
    video_export_height: Number(el("video_export_height")?.value || DEFAULTS.video_export_height),
    video_export_fps: Number(el("video_export_fps")?.value || DEFAULTS.video_export_fps),
    video_export_bg_color: String(el("video_export_bg_color")?.value || DEFAULTS.video_export_bg_color).trim(),
  };
}

function normalize(raw = {}) {
  const fallback = getMainSettingsDefaults();
  const nn = (v, fb, min = 0) => { const n = Number(v); return Number.isFinite(n) && n >= min ? n : fb; };
  return {
    video_export_min_slide_sec: nn(raw.video_export_min_slide_sec, fallback.video_export_min_slide_sec, 0.04),
    video_export_tail_pad_sec: nn(raw.video_export_tail_pad_sec, fallback.video_export_tail_pad_sec),
    video_export_thumbnail_duration_sec: nn(raw.video_export_thumbnail_duration_sec, fallback.video_export_thumbnail_duration_sec, 0.04),
    video_export_thumbnail_fade_sec: nn(raw.video_export_thumbnail_fade_sec, fallback.video_export_thumbnail_fade_sec),
    video_export_thumbnail_text_leadin_sec: nn(raw.video_export_thumbnail_text_leadin_sec, fallback.video_export_thumbnail_text_leadin_sec),
    video_export_intro_white_sec: nn(raw.video_export_intro_white_sec, fallback.video_export_intro_white_sec),
    video_export_intro_fade_sec: nn(raw.video_export_intro_fade_sec, fallback.video_export_intro_fade_sec),
    video_export_intro_color: String(raw.video_export_intro_color || fallback.video_export_intro_color || "white").trim(),
    video_export_outro_hold_sec: nn(raw.video_export_outro_hold_sec, fallback.video_export_outro_hold_sec),
    video_export_outro_fade_sec: nn(raw.video_export_outro_fade_sec, fallback.video_export_outro_fade_sec),
    video_export_outro_fade_color: String(raw.video_export_outro_fade_color || fallback.video_export_outro_fade_color || "black").trim(),
    video_export_outro_black_sec: nn(raw.video_export_outro_black_sec, fallback.video_export_outro_black_sec),
    video_export_width: nn(raw.video_export_width, fallback.video_export_width, 1),
    video_export_height: nn(raw.video_export_height, fallback.video_export_height, 1),
    video_export_fps: nn(raw.video_export_fps, fallback.video_export_fps, 1),
    video_export_bg_color: String(raw.video_export_bg_color || fallback.video_export_bg_color || "white").trim(),
  };
}

const form = reactive(normalize(readFromStorage() || getMainSettingsDefaults()));

function persist() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(form)); } catch { /* ignore */ }
}

watch(() => props.open, (val) => {
  if (val) {
    const stored = readFromStorage();
    Object.assign(form, normalize(stored || getMainSettingsDefaults()));
  }
});

function save() {
  Object.assign(form, normalize(form));
  persist();
  emit("save", { ...form });
}

function reset() {
  Object.assign(form, normalize(getMainSettingsDefaults()));
  persist();
}

function getSettings() {
  Object.assign(form, normalize(form));
  persist();
  return { ...form };
}

defineExpose({ getSettings });
</script>
