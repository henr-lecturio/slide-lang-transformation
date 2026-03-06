<template>
  <AppModal :open="open" variant="picker" aria-label="Image Lab test settings" @close="$emit('close')">
    <div class="video-picker-dialog lab-settings-dialog">
      <div class="modal-head lab-settings-head">
        <h3>Image Lab Test Settings</h3>
        <div class="lab-settings-head-actions">
          <button type="button" @click="reset">Reset from Settings</button>
          <button type="button" @click="save">Save Test Settings</button>
          <button type="button" @click="saveToMain">Save to Main Settings</button>
          <button class="modal-close" type="button" aria-label="Close test settings" @click="$emit('close')">&times;</button>
        </div>
      </div>
      <div class="status-modal-body lab-settings-body">
        <div class="muted">These values apply only to <strong>Image Lab</strong> tests and never modify the main settings.</div>
        <div class="step-sections lab-step-sections">

          <!-- Slide Edit -->
          <section class="step-section is-forced" :class="{ 'is-open': sections.slideEdit }">
            <div class="step-section-head">
              <div class="step-section-title-wrap">
                <div class="step-section-heading">
                  <label class="step-switch is-static step-switch-icononly"><input type="checkbox" checked disabled aria-label="Slide Edit test settings" /></label>
                  <h3>Slide Edit</h3>
                  <button type="button" class="step-section-toggle lab-step-section-toggle" :aria-expanded="sections.slideEdit ? 'true' : 'false'" @click="sections.slideEdit = !sections.slideEdit">
                    <span class="step-section-chevron" aria-hidden="true"></span>
                  </button>
                </div>
                <div class="step-section-subtitle muted">Isolated test values for <strong>Image Lab</strong> Slide Edit only.</div>
              </div>
            </div>
            <div class="step-section-body" :hidden="!sections.slideEdit">
              <div class="settings-list">
                <div class="settings-row">
                  <label class="settings-key" for="lab_gemini_edit_model_v">LAB_SLIDE_EDIT_MODEL</label>
                  <div class="settings-value">
                    <select id="lab_gemini_edit_model_v" v-model="form.slide_edit_model">
                      <option v-for="m in ALLOWED_IMAGE_MODELS" :key="m" :value="m">{{ m }}</option>
                    </select>
                  </div>
                </div>
                <div class="settings-row">
                  <label class="settings-key" for="lab_gemini_edit_prompt_v">LAB_SLIDE_EDIT_PROMPT</label>
                  <div class="settings-value"><textarea id="lab_gemini_edit_prompt_v" rows="5" v-model="form.slide_edit_prompt"></textarea></div>
                </div>
              </div>
            </div>
          </section>

          <!-- Slide Translate -->
          <section class="step-section is-forced" :class="{ 'is-open': sections.slideTranslate }">
            <div class="step-section-head">
              <div class="step-section-title-wrap">
                <div class="step-section-heading">
                  <label class="step-switch is-static step-switch-icononly"><input type="checkbox" checked disabled aria-label="Slide Translate test settings" /></label>
                  <h3>Slide Translate</h3>
                  <button type="button" class="step-section-toggle lab-step-section-toggle" :aria-expanded="sections.slideTranslate ? 'true' : 'false'" @click="sections.slideTranslate = !sections.slideTranslate">
                    <span class="step-section-chevron" aria-hidden="true"></span>
                  </button>
                </div>
                <div class="step-section-subtitle muted">Uses the current <strong>FINAL_SLIDE_TRANSLATION_MODE</strong> from Settings.</div>
              </div>
            </div>
            <div class="step-section-body" :hidden="!sections.slideTranslate">
              <div class="settings-list">
                <div class="settings-row">
                  <label class="settings-key" for="lab_target_language_v">LAB_TARGET_LANGUAGE</label>
                  <div class="settings-value">
                    <select id="lab_target_language_v" v-model="form.target_language">
                      <option v-if="languageOptions.length === 0" value="">No languages available</option>
                      <option v-for="opt in languageOptions" :key="opt.tts_language_code" :value="opt.label">
                        {{ opt.launch_readiness ? `${opt.label} [${opt.tts_language_code}] (${opt.launch_readiness})` : `${opt.label} [${opt.tts_language_code}]` }}
                      </option>
                    </select>
                  </div>
                </div>
                <div class="settings-row">
                  <label class="settings-key" for="lab_translate_model_v">LAB_SLIDE_TRANSLATE_MODEL</label>
                  <div class="settings-value">
                    <select id="lab_translate_model_v" v-model="form.slide_translate_model" :disabled="!isGeminiTranslateMode">
                      <option v-for="m in ALLOWED_IMAGE_MODELS" :key="m" :value="m">{{ m }}</option>
                    </select>
                  </div>
                </div>
                <div class="settings-row">
                  <label class="settings-key" for="lab_translate_prompt_v">LAB_SLIDE_TRANSLATE_PROMPT</label>
                  <div class="settings-value"><textarea id="lab_translate_prompt_v" rows="5" v-model="form.slide_translate_prompt" :disabled="!isGeminiTranslateMode"></textarea></div>
                </div>
                <div class="settings-row termbase-settings-row">
                  <label class="settings-key" for="lab_styles_json_v">LAB_SLIDE_TRANSLATE_STYLING</label>
                  <div class="settings-value">
                    <div class="output-info-panel termbase-editor-panel" :class="{ 'is-open': styleEditorOpen }">
                      <button class="output-info-toggle" type="button" :aria-expanded="styleEditorOpen ? 'true' : 'false'" @click="styleEditorOpen = !styleEditorOpen" :disabled="!isDeterministicMode">
                        <span>Text Styling</span>
                        <span class="step-section-chevron" aria-hidden="true"></span>
                      </button>
                      <div class="output-info-body" :hidden="!styleEditorOpen">
                        <div class="termbase-table-wrap">
                          <table class="termbase-table slide-style-table">
                            <thead>
                              <tr><th>Key</th><th>Weight</th><th>Font Size</th><th>Min Font</th><th>Line Spacing</th><th>Color</th><th>Padding</th></tr>
                            </thead>
                            <tbody>
                              <tr v-for="(row, i) in styleRows" :key="i">
                                <td><input type="text" :value="row.display_key" readonly /></td>
                                <td>
                                  <select v-model="row.font_weight" :disabled="!isDeterministicMode" @change="syncStylesJson">
                                    <option>Regular</option><option>Medium</option><option>Bold</option>
                                  </select>
                                </td>
                                <td><input type="number" min="1" step="1" v-model="row.font_size" :disabled="!isDeterministicMode" @input="syncStylesJson" /></td>
                                <td><input type="number" min="1" step="1" v-model="row.min_font_size" :disabled="!isDeterministicMode" @input="syncStylesJson" /></td>
                                <td><input type="number" min="0" step="0.01" v-model="row.line_spacing_ratio" :disabled="!isDeterministicMode" @input="syncStylesJson" /></td>
                                <td><input type="text" placeholder="auto or #RRGGBB" v-model="row.text_color" :disabled="!isDeterministicMode" @input="syncStylesJson" /></td>
                                <td><input type="text" placeholder="top right bottom left" v-model="row.padding" :disabled="!isDeterministicMode" @input="syncStylesJson" /></td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                    <textarea id="lab_styles_json_v" rows="12" spellcheck="false" hidden v-model="form.slide_translate_styles_json"></textarea>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- Slide Upscale -->
          <section class="step-section is-forced" :class="{ 'is-open': sections.slideUpscale }">
            <div class="step-section-head">
              <div class="step-section-title-wrap">
                <div class="step-section-heading">
                  <label class="step-switch is-static step-switch-icononly"><input type="checkbox" checked disabled aria-label="Slide Upscale test settings" /></label>
                  <h3>Slide Upscale</h3>
                  <button type="button" class="step-section-toggle lab-step-section-toggle" :aria-expanded="sections.slideUpscale ? 'true' : 'false'" @click="sections.slideUpscale = !sections.slideUpscale">
                    <span class="step-section-chevron" aria-hidden="true"></span>
                  </button>
                </div>
                <div class="step-section-subtitle muted">Isolated test values for <strong>Image Lab</strong> Slide Upscale only.</div>
              </div>
            </div>
            <div class="step-section-body" :hidden="!sections.slideUpscale">
              <div class="settings-list">
                <div class="settings-row">
                  <label class="settings-key" for="lab_upscale_mode_v">LAB_SLIDE_UPSCALE_MODE</label>
                  <div class="settings-value">
                    <select id="lab_upscale_mode_v" v-model="form.slide_upscale_mode">
                      <option value="swin2sr">Local Swin2SR</option>
                      <option value="replicate_nightmare_realesrgan">Replicate nightmareai/real-esrgan</option>
                    </select>
                  </div>
                </div>
                <div class="settings-row lab-upscale-local-row" :hidden="form.slide_upscale_mode !== 'swin2sr'">
                  <label class="settings-key" for="lab_upscale_model_v">LAB_LOCAL_UPSCALE_MODEL</label>
                  <div class="settings-value"><input id="lab_upscale_model_v" type="text" v-model="form.slide_upscale_model" /></div>
                </div>
                <div class="settings-row lab-upscale-local-row" :hidden="form.slide_upscale_mode !== 'swin2sr'">
                  <label class="settings-key" for="lab_upscale_device_v">LAB_LOCAL_UPSCALE_DEVICE</label>
                  <div class="settings-value">
                    <select id="lab_upscale_device_v" v-model="form.slide_upscale_device">
                      <option value="auto">auto</option><option value="cuda">cuda</option><option value="cpu">cpu</option>
                    </select>
                  </div>
                </div>
                <div class="settings-row lab-upscale-local-row" :hidden="form.slide_upscale_mode !== 'swin2sr'">
                  <label class="settings-key" for="lab_upscale_tile_size_v">LAB_LOCAL_UPSCALE_TILE_SIZE</label>
                  <div class="settings-value"><input id="lab_upscale_tile_size_v" type="number" min="0" step="1" v-model.number="form.slide_upscale_tile_size" /></div>
                </div>
                <div class="settings-row lab-upscale-local-row" :hidden="form.slide_upscale_mode !== 'swin2sr'">
                  <label class="settings-key" for="lab_upscale_tile_overlap_v">LAB_LOCAL_UPSCALE_TILE_OVERLAP</label>
                  <div class="settings-value"><input id="lab_upscale_tile_overlap_v" type="number" min="0" step="1" v-model.number="form.slide_upscale_tile_overlap" /></div>
                </div>
                <div class="settings-row lab-upscale-replicate-row" :hidden="form.slide_upscale_mode !== 'replicate_nightmare_realesrgan'">
                  <label class="settings-key" for="lab_rep_model_v">LAB_REPLICATE_MODEL_REF</label>
                  <div class="settings-value"><input id="lab_rep_model_v" type="text" v-model="form.replicate_model_ref" /></div>
                </div>
                <div class="settings-row lab-upscale-replicate-row" :hidden="form.slide_upscale_mode !== 'replicate_nightmare_realesrgan'">
                  <label class="settings-key" for="lab_rep_version_v">LAB_REPLICATE_VERSION_ID</label>
                  <div class="settings-value"><input id="lab_rep_version_v" type="text" v-model="form.replicate_version_id" /></div>
                </div>
              </div>
            </div>
          </section>

        </div>
      </div>
    </div>
  </AppModal>
</template>

<script setup>
import { reactive, ref, computed, watch } from "vue";
import AppModal from "../components/AppModal.vue";

const STORAGE_KEY = "slide-transform-lab-test-settings";
const ALLOWED_IMAGE_MODELS = [
  "gemini-3.1-flash-image-preview",
  "gemini-3-pro-image-preview",
  "gemini-2.5-flash-image",
];
const ALLOWED_IMAGE_MODELS_SET = new Set(ALLOWED_IMAGE_MODELS);

const props = defineProps({
  open: { type: Boolean, default: false },
  ttsLanguageOptions: { type: Array, default: () => [] },
});

const emit = defineEmits(["close", "save", "save-to-main"]);

const sections = reactive({ slideEdit: false, slideTranslate: false, slideUpscale: false });
const styleEditorOpen = ref(false);
const styleRows = ref([]);

const languageOptions = computed(() => props.ttsLanguageOptions);

const translationMode = computed(() => {
  const el = document.getElementById("final_slide_translation_mode");
  return String(el?.value || "gemini").trim().toLowerCase();
});

const isGeminiTranslateMode = computed(() => translationMode.value !== "deterministic_glossary");
const isDeterministicMode = computed(() => translationMode.value === "deterministic_glossary");

function getMainEl(id) { return document.getElementById(id); }

function selectedMainTargetLanguageLabel() {
  const code = String(getMainEl("final_slide_target_language")?.value || "").trim();
  if (!code) return "";
  const option = props.ttsLanguageOptions.find((item) => item.tts_language_code === code);
  return String(option?.label || "").trim();
}

function defaultsFromMainUi() {
  return {
    slide_edit_model: (getMainEl("gemini_edit_model")?.value || "gemini-3-pro-image-preview").trim(),
    slide_edit_prompt: getMainEl("gemini_edit_prompt")?.value || "",
    target_language: selectedMainTargetLanguageLabel(),
    slide_translate_model: (getMainEl("gemini_translate_model")?.value || "gemini-3-pro-image-preview").trim(),
    slide_extract_model: (getMainEl("gemini_extract_model")?.value || "").trim(),
    slide_extract_prompt: getMainEl("gemini_slide_extract_prompt")?.value || "",
    slide_translate_prompt: getMainEl("gemini_slide_translate_prompt")?.value || "",
    slide_render_prompt: getMainEl("gemini_slide_render_prompt")?.value || "",
    slide_translate_styles_json: String(getMainEl("slide_translate_styles_json")?.value || "").trim(),
    slide_upscale_mode: (getMainEl("final_slide_upscale_mode")?.value || "swin2sr").trim(),
    slide_upscale_model: (getMainEl("final_slide_upscale_model")?.value || "caidas/swin2SR-classical-sr-x4-64").trim(),
    slide_upscale_device: (getMainEl("final_slide_upscale_device")?.value || "auto").trim(),
    slide_upscale_tile_size: Number(getMainEl("final_slide_upscale_tile_size")?.value || 256),
    slide_upscale_tile_overlap: Number(getMainEl("final_slide_upscale_tile_overlap")?.value || 24),
    replicate_model_ref: (getMainEl("replicate_nightmare_realesrgan_model_ref")?.value || "nightmareai/real-esrgan").trim(),
    replicate_version_id: (getMainEl("replicate_nightmare_realesrgan_version_id")?.value || "f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa").trim(),
  };
}

function normalize(raw = {}) {
  const fb = defaultsFromMainUi();
  const next = {
    slide_edit_model: String(raw.slide_edit_model || fb.slide_edit_model || "gemini-3-pro-image-preview").trim(),
    slide_edit_prompt: String(raw.slide_edit_prompt ?? fb.slide_edit_prompt ?? ""),
    target_language: String(raw.target_language || fb.target_language || "").trim(),
    slide_translate_model: String(raw.slide_translate_model || fb.slide_translate_model || "gemini-3-pro-image-preview").trim(),
    slide_translate_prompt: String(raw.slide_translate_prompt ?? fb.slide_translate_prompt ?? ""),
    slide_translate_styles_json: String(raw.slide_translate_styles_json ?? fb.slide_translate_styles_json ?? "").trim(),
    slide_upscale_mode: String(raw.slide_upscale_mode || fb.slide_upscale_mode || "swin2sr").trim(),
    slide_upscale_model: String(raw.slide_upscale_model || fb.slide_upscale_model || "caidas/swin2SR-classical-sr-x4-64").trim(),
    slide_upscale_device: String(raw.slide_upscale_device || fb.slide_upscale_device || "auto").trim(),
    slide_upscale_tile_size: Number(raw.slide_upscale_tile_size ?? fb.slide_upscale_tile_size ?? 256),
    slide_upscale_tile_overlap: Number(raw.slide_upscale_tile_overlap ?? fb.slide_upscale_tile_overlap ?? 24),
    replicate_model_ref: String(raw.replicate_model_ref || fb.replicate_model_ref || "nightmareai/real-esrgan").trim(),
    replicate_version_id: String(raw.replicate_version_id || fb.replicate_version_id || "f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa").trim(),
  };
  if (!ALLOWED_IMAGE_MODELS_SET.has(next.slide_edit_model)) next.slide_edit_model = "gemini-3-pro-image-preview";
  if (!ALLOWED_IMAGE_MODELS_SET.has(next.slide_translate_model)) next.slide_translate_model = "gemini-3-pro-image-preview";
  if (!["swin2sr", "replicate_nightmare_realesrgan"].includes(next.slide_upscale_mode)) next.slide_upscale_mode = "swin2sr";
  if (!Number.isFinite(next.slide_upscale_tile_size) || next.slide_upscale_tile_size < 0) next.slide_upscale_tile_size = 256;
  if (!Number.isFinite(next.slide_upscale_tile_overlap) || next.slide_upscale_tile_overlap < 0) next.slide_upscale_tile_overlap = 24;
  return next;
}

function readFromStorage() {
  try { const raw = localStorage.getItem(STORAGE_KEY); return raw ? JSON.parse(raw) : null; } catch { return null; }
}

function persist() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(form)); } catch { /* ignore */ }
}

const form = reactive(normalize(readFromStorage() || defaultsFromMainUi()));

// Style editor helpers
function parseStylesJson(jsonText) {
  const text = String(jsonText || "").trim();
  if (!text) return { version: 1, defaults: {}, roles: {}, slots: {} };
  try {
    const p = JSON.parse(text);
    return {
      version: Number(p?.version) > 0 ? Number(p.version) : 1,
      defaults: p?.defaults && typeof p.defaults === "object" ? structuredClone(p.defaults) : {},
      roles: p?.roles && typeof p.roles === "object" ? structuredClone(p.roles) : {},
      slots: p?.slots && typeof p.slots === "object" ? structuredClone(p.slots) : {},
    };
  } catch { return { version: 1, defaults: {}, roles: {}, slots: {} }; }
}

function buildStyleRows(model) {
  const rows = [{ scope_type: "defaults", scope_key: "defaults", display_key: "defaults", style: model.defaults || {} }];
  for (const [k, v] of Object.entries(model.roles || {})) rows.push({ scope_type: "role", scope_key: k, display_key: k, style: v || {} });
  for (const [k, v] of Object.entries(model.slots || {})) rows.push({ scope_type: "slot", scope_key: k, display_key: k, style: v || {} });
  return rows;
}

function styleToVisibleValues(style = {}) {
  let weight = "Regular";
  const ew = String(style.font_weight ?? "").trim().toLowerCase();
  if (ew === "medium") weight = "Medium";
  else if (ew === "bold") weight = "Bold";
  else if (ew === "regular") weight = "Regular";
  else {
    const fp = String(style.font_path ?? "").toLowerCase();
    if (fp.includes("bold")) weight = "Bold";
    else if (fp.includes("medium")) weight = "Medium";
  }
  const colorMode = String(style.text_color_mode ?? "").trim();
  const color = String(style.text_color ?? "").trim();
  let displayColor = "auto";
  if (colorMode === "fixed" && color) displayColor = color;
  else if (color && color.toLowerCase() !== "auto") displayColor = color;

  let padding = String(style.padding ?? "").trim();
  if (!padding) {
    const t = style.box_padding_top_ratio ?? style.box_padding_y_ratio;
    const r = style.box_padding_right_ratio ?? style.box_padding_x_ratio;
    const b = style.box_padding_bottom_ratio ?? style.box_padding_y_ratio;
    const l = style.box_padding_left_ratio ?? style.box_padding_x_ratio;
    const vals = [t, r, b, l].map((v) => v == null || v === "" ? "" : String(v).trim());
    if (vals.every((v) => v !== "")) padding = vals.join(" ");
  }

  return {
    font_weight: weight,
    font_size: style.font_size == null ? "" : String(style.font_size),
    min_font_size: style.min_font_size == null ? "" : String(style.min_font_size),
    line_spacing_ratio: style.line_spacing_ratio == null ? "" : String(style.line_spacing_ratio),
    text_color: displayColor,
    padding,
  };
}

function refreshStyleRows() {
  const model = parseStylesJson(form.slide_translate_styles_json);
  styleRows.value = buildStyleRows(model).map((r) => ({
    ...r,
    ...styleToVisibleValues(r.style),
  }));
}

function syncStylesJson() {
  const model = parseStylesJson(form.slide_translate_styles_json);
  for (const row of styleRows.value) {
    const style = row.scope_type === "defaults" ? model.defaults : row.scope_type === "role" ? model.roles?.[row.scope_key] : model.slots?.[row.scope_key];
    if (!style || typeof style !== "object") continue;
    style.font_size_mode = "fixed";
    const w = String(row.font_weight ?? "").trim().toLowerCase();
    if (["regular", "medium", "bold"].includes(w)) style.font_weight = w; else delete style.font_weight;
    const fs = String(row.font_size ?? "").trim(); if (fs) { const n = Number(fs); if (Number.isFinite(n)) style.font_size = Math.round(n); else delete style.font_size; } else delete style.font_size;
    const mfs = String(row.min_font_size ?? "").trim(); if (mfs) { const n = Number(mfs); if (Number.isFinite(n)) style.min_font_size = Math.round(n); else delete style.min_font_size; } else delete style.min_font_size;
    const lsr = String(row.line_spacing_ratio ?? "").trim(); if (lsr) { const n = Number(lsr); if (Number.isFinite(n)) style.line_spacing_ratio = n; else delete style.line_spacing_ratio; } else delete style.line_spacing_ratio;
    const tc = String(row.text_color ?? "").trim();
    if (!tc || tc.toLowerCase() === "auto" || tc.toLowerCase() === "inherit") { delete style.text_color; if (String(style.text_color_mode ?? "").trim() === "fixed") delete style.text_color_mode; }
    else { style.text_color = tc; style.text_color_mode = "fixed"; }
    const pad = String(row.padding ?? "").trim().replace(/,/g, " ");
    delete style.padding; delete style.box_padding_x_ratio; delete style.box_padding_y_ratio;
    delete style.box_padding_top_ratio; delete style.box_padding_right_ratio; delete style.box_padding_bottom_ratio; delete style.box_padding_left_ratio;
    if (pad) style.padding = pad;
  }
  form.slide_translate_styles_json = JSON.stringify(model, null, 2);
}

watch(() => props.open, (val) => {
  if (val) {
    const stored = readFromStorage();
    Object.assign(form, normalize(stored || defaultsFromMainUi()));
    refreshStyleRows();
  }
});

function save() {
  syncStylesJson();
  Object.assign(form, normalize(form));
  persist();
  emit("save", { ...form });
}

function reset() {
  Object.assign(form, normalize(defaultsFromMainUi()));
  persist();
  refreshStyleRows();
}

function saveToMain() {
  syncStylesJson();
  Object.assign(form, normalize(form));
  persist();
  emit("save-to-main", { ...form });
}

function getSettings() {
  syncStylesJson();
  Object.assign(form, normalize(form));
  persist();
  return { ...form };
}

function buildSettingsSummary() {
  const s = normalize(form);
  const modeRaw = String(getMainEl("final_slide_translation_mode")?.value || "gemini").trim().toLowerCase();
  const modeLabel = modeRaw === "deterministic_glossary" ? "Google OCR + Glossary" : modeRaw === "gemini" ? "nano banana" : modeRaw || "none";
  return [`edit=${s.slide_edit_model || "-"}`, `translate=${s.target_language || "-"} [${modeLabel}]`, `upscale=${s.slide_upscale_mode || "-"}`].join(" | ");
}

defineExpose({ getSettings, buildSettingsSummary });
</script>
