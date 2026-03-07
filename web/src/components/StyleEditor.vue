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
import {
  parseStylesJson, displayColor, displayPadding, inferWeight,
  deletePaddingKeys, normalizePadding, parseIntOrUndef, parseFloatOrUndef,
  styleToVisibleValues,
} from "../utils/styleEditorUtils.js";

const props = defineProps({
  modelValue: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue"]);

const editorOpen = ref(false);
const visibleRows = ref([]);
let modelSnapshot = { version: 1, defaults: {}, roles: {}, slots: {} };

function buildVisibleRows(model) {
  const entries = [
    { scopeType: "defaults", scopeKey: "defaults", displayKey: "defaults", style: model.defaults || {} },
    ...Object.entries(model.roles || {}).map(([key, val]) => ({ scopeType: "role", scopeKey: key, displayKey: key, style: val || {} })),
    ...Object.entries(model.slots || {}).map(([key, val]) => ({ scopeType: "slot", scopeKey: key, displayKey: key, style: val || {} })),
  ];
  return entries.map((entry) => {
    const vis = styleToVisibleValues(entry.style);
    return {
      scopeType: entry.scopeType,
      scopeKey: entry.scopeKey,
      displayKey: entry.displayKey,
      ...vis,
      _initialWeight: vis.font_weight,
      _initialFontSize: vis.font_size,
      _initialMinFontSize: vis.min_font_size,
      _initialLineSpacing: vis.line_spacing_ratio,
      _initialColor: vis.text_color,
      _initialPadding: vis.padding,
    };
  });
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
