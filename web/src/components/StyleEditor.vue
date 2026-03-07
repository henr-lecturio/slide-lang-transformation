<template>
  <CollapsiblePanel title="Text Styling" name="styleEditor" v-model:open="editorOpen" :disabled="disabled" panel-class="termbase-editor-panel">
      <div class="termbase-table-wrap">
        <table class="termbase-table slide-style-table">
          <thead>
            <tr>
              <th>Key</th>
              <th>Weight</th>
              <th>Font Size</th>
              <th>Min Font</th>
              <th>Line Spacing</th>
              <th>Color</th>
              <th>Padding</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in visibleRows" :key="row.scopeType + ':' + row.scopeKey">
              <td><input type="text" readonly :value="row.displayKey" /></td>
              <td>
                <select v-model="row.font_weight" :disabled="disabled" @change="syncJson">
                  <option value="Regular">Regular</option>
                  <option value="Medium">Medium</option>
                  <option value="Bold">Bold</option>
                </select>
              </td>
              <td><input type="number" min="1" step="1" v-model="row.font_size" :disabled="disabled" @input="syncJson" @change="syncJson" /></td>
              <td><input type="number" min="1" step="1" v-model="row.min_font_size" :disabled="disabled" @input="syncJson" @change="syncJson" /></td>
              <td><input type="number" min="0" step="0.01" v-model="row.line_spacing_ratio" :disabled="disabled" @input="syncJson" @change="syncJson" /></td>
              <td><input type="text" placeholder="auto or #RRGGBB" v-model="row.text_color" :disabled="disabled" @input="syncJson" @change="syncJson" /></td>
              <td><input type="text" placeholder="top right bottom left" v-model="row.padding" :disabled="disabled" @input="syncJson" @change="syncJson" /></td>
            </tr>
          </tbody>
        </table>
      </div>
  </CollapsiblePanel>
  <textarea id="slide_translate_styles_json" :value="modelValue" rows="12" spellcheck="false" hidden></textarea>
</template>

<script setup>
import { ref, watch, onMounted } from "vue";
import CollapsiblePanel from "./CollapsiblePanel.vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue"]);

const editorOpen = ref(false);
const visibleRows = ref([]);
let modelSnapshot = { version: 1, defaults: {}, roles: {}, slots: {} };

function parseStylesJson(jsonText) {
  const text = String(jsonText || "").trim();
  if (!text) return { version: 1, defaults: {}, roles: {}, slots: {} };
  try {
    const p = JSON.parse(text);
    return {
      version: Number(p?.version) > 0 ? Number(p.version) : 1,
      defaults: p && typeof p.defaults === "object" && p.defaults ? structuredClone(p.defaults) : {},
      roles: p && typeof p.roles === "object" && p.roles ? structuredClone(p.roles) : {},
      slots: p && typeof p.slots === "object" && p.slots ? structuredClone(p.slots) : {},
    };
  } catch {
    return { version: 1, defaults: {}, roles: {}, slots: {} };
  }
}

function displayColor(style = {}) {
  const mode = String(style.text_color_mode ?? "").trim();
  const color = String(style.text_color ?? "").trim();
  if (mode === "fixed" && color) return color;
  if (color && color.toLowerCase() !== "auto") return color;
  return "auto";
}

function displayPadding(style = {}) {
  const padding = String(style.padding ?? "").trim();
  if (padding) return padding;
  const top = style.box_padding_top_ratio ?? style.box_padding_y_ratio;
  const right = style.box_padding_right_ratio ?? style.box_padding_x_ratio;
  const bottom = style.box_padding_bottom_ratio ?? style.box_padding_y_ratio;
  const left = style.box_padding_left_ratio ?? style.box_padding_x_ratio;
  const values = [top, right, bottom, left].map((v) => (v === undefined || v === null || v === "" ? "" : String(v).trim()));
  if (values.every((v) => v !== "")) return values.join(" ");
  return "";
}

function inferWeight(style = {}) {
  const explicit = String(style.font_weight ?? "").trim().toLowerCase();
  if (explicit === "medium") return "Medium";
  if (explicit === "bold") return "Bold";
  if (explicit === "regular") return "Regular";
  const fontPath = String(style.font_path ?? "").toLowerCase();
  if (fontPath.includes("bold")) return "Bold";
  if (fontPath.includes("medium")) return "Medium";
  return "Regular";
}

function buildVisibleRows(model) {
  const entries = [
    { scopeType: "defaults", scopeKey: "defaults", displayKey: "defaults", style: model.defaults || {} },
    ...Object.entries(model.roles || {}).map(([key, val]) => ({ scopeType: "role", scopeKey: key, displayKey: key, style: val || {} })),
    ...Object.entries(model.slots || {}).map(([key, val]) => ({ scopeType: "slot", scopeKey: key, displayKey: key, style: val || {} })),
  ];
  return entries.map((entry) => ({
    scopeType: entry.scopeType,
    scopeKey: entry.scopeKey,
    displayKey: entry.displayKey,
    font_weight: inferWeight(entry.style),
    font_size: entry.style.font_size === undefined || entry.style.font_size === null ? "" : String(entry.style.font_size),
    min_font_size: entry.style.min_font_size === undefined || entry.style.min_font_size === null ? "" : String(entry.style.min_font_size),
    line_spacing_ratio: entry.style.line_spacing_ratio === undefined || entry.style.line_spacing_ratio === null ? "" : String(entry.style.line_spacing_ratio),
    text_color: displayColor(entry.style),
    padding: displayPadding(entry.style),
    _initialWeight: inferWeight(entry.style),
    _initialFontSize: entry.style.font_size === undefined || entry.style.font_size === null ? "" : String(entry.style.font_size),
    _initialMinFontSize: entry.style.min_font_size === undefined || entry.style.min_font_size === null ? "" : String(entry.style.min_font_size),
    _initialLineSpacing: entry.style.line_spacing_ratio === undefined || entry.style.line_spacing_ratio === null ? "" : String(entry.style.line_spacing_ratio),
    _initialColor: displayColor(entry.style),
    _initialPadding: displayPadding(entry.style),
  }));
}

function parseIntOrUndef(value) {
  const text = String(value ?? "").trim();
  if (!text) return undefined;
  const num = Number(text);
  return Number.isFinite(num) ? Math.round(num) : undefined;
}

function parseFloatOrUndef(value) {
  const text = String(value ?? "").trim();
  if (!text) return undefined;
  const num = Number(text);
  return Number.isFinite(num) ? num : undefined;
}

function normalizePadding(value) {
  const text = String(value ?? "").trim().replace(/,/g, " ");
  if (!text) return "";
  return text.split(/\s+/).filter(Boolean).join(" ");
}

function deletePaddingKeys(style) {
  delete style.padding;
  delete style.box_padding_x_ratio;
  delete style.box_padding_y_ratio;
  delete style.box_padding_top_ratio;
  delete style.box_padding_right_ratio;
  delete style.box_padding_bottom_ratio;
  delete style.box_padding_left_ratio;
}

function syncJson() {
  const payload = structuredClone(modelSnapshot);
  for (const row of visibleRows.value) {
    const style =
      row.scopeType === "defaults" ? payload.defaults
        : row.scopeType === "role" ? payload.roles?.[row.scopeKey]
          : payload.slots?.[row.scopeKey];
    if (!style || typeof style !== "object") continue;
    style.font_size_mode = "fixed";

    if (String(row.font_weight ?? "") !== String(row._initialWeight ?? "")) {
      const w = String(row.font_weight ?? "").trim().toLowerCase();
      if (["regular", "medium", "bold"].includes(w)) style.font_weight = w;
      else delete style.font_weight;
    }
    if (String(row.font_size ?? "") !== String(row._initialFontSize ?? "")) {
      const v = parseIntOrUndef(row.font_size);
      if (v === undefined) delete style.font_size; else style.font_size = v;
    }
    if (String(row.min_font_size ?? "") !== String(row._initialMinFontSize ?? "")) {
      const v = parseIntOrUndef(row.min_font_size);
      if (v === undefined) delete style.min_font_size; else style.min_font_size = v;
    }
    if (String(row.line_spacing_ratio ?? "") !== String(row._initialLineSpacing ?? "")) {
      const v = parseFloatOrUndef(row.line_spacing_ratio);
      if (v === undefined) delete style.line_spacing_ratio; else style.line_spacing_ratio = v;
    }
    if (String(row.text_color ?? "") !== String(row._initialColor ?? "")) {
      const color = String(row.text_color ?? "").trim();
      if (!color || color.toLowerCase() === "auto" || color.toLowerCase() === "inherit") {
        delete style.text_color;
        if (String(style.text_color_mode ?? "").trim() === "fixed") delete style.text_color_mode;
      } else {
        style.text_color = color;
        style.text_color_mode = "fixed";
      }
    }
    if (String(row.padding ?? "") !== String(row._initialPadding ?? "")) {
      const padding = normalizePadding(row.padding);
      deletePaddingKeys(style);
      if (padding) style.padding = padding;
    }
  }
  emit("update:modelValue", JSON.stringify(payload, null, 2));
}

function loadFromJson(jsonText) {
  modelSnapshot = parseStylesJson(jsonText);
  visibleRows.value = buildVisibleRows(modelSnapshot);
}

watch(() => props.modelValue, (newVal) => {
  loadFromJson(newVal);
});

onMounted(() => {
  loadFromJson(props.modelValue);
});
</script>
