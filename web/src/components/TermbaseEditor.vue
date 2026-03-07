<template>
  <CollapsiblePanel title="Translation Termbase Table" name="termbaseEditor" v-model:open="editorOpen" panel-class="termbase-editor-panel">
      <div class="termbase-editor-toolbar">
        <button type="button" @click="addRow">Add Row</button>
      </div>
      <div class="termbase-table-wrap">
        <table class="termbase-table">
          <thead>
            <tr>
              <th>Source Text</th>
              <th>Target Language</th>
              <th>Target Text</th>
              <th>Case Sensitive</th>
              <th></th>
            </tr>
          </thead>
          <tbody id="termbase-table-body">
            <tr v-for="(row, index) in rows" :key="index">
              <td><input type="text" v-model="row.source_text" @input="syncCsv" /></td>
              <td>
                <select v-model="row.target_language" @change="syncCsv">
                  <option v-for="choice in languageChoices(row.target_language)" :key="choice.value" :value="choice.value">{{ choice.label }}</option>
                </select>
              </td>
              <td><input type="text" v-model="row.target_text" @input="syncCsv" /></td>
              <td>
                <select v-model="row.case_sensitive" @change="syncCsv">
                  <option value="0">No</option>
                  <option value="1">Yes</option>
                </select>
              </td>
              <td class="termbase-table-actions">
                <button type="button" class="termbase-remove-row" @click="removeRow(index)">Remove</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
  </CollapsiblePanel>
  <textarea id="translation_termbase_csv" :value="modelValue" rows="12" spellcheck="false" hidden></textarea>
</template>

<script setup>
import { ref, watch, onMounted } from "vue";
import CollapsiblePanel from "./CollapsiblePanel.vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  languageOptions: { type: Array, default: () => [] },
});

const emit = defineEmits(["update:modelValue"]);

const editorOpen = ref(false);
const rows = ref([]);

function parseCsvLine(line) {
  const out = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === "," && !inQuotes) {
      out.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  out.push(current);
  return out;
}

function parseTermbaseCsv(csvText) {
  const text = String(csvText || "").replace(/\r\n/g, "\n").trim();
  if (!text) return [];
  const lines = text.split("\n").filter(Boolean);
  if (lines.length === 0) return [];
  const header = parseCsvLine(lines[0]).map((v) => v.trim());
  const indexByKey = new Map(header.map((key, index) => [key, index]));
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    return {
      source_text: values[indexByKey.get("source_text") ?? -1] ?? "",
      target_language: values[indexByKey.get("target_language") ?? -1] ?? "",
      target_text: values[indexByKey.get("target_text") ?? -1] ?? "",
      case_sensitive: values[indexByKey.get("case_sensitive") ?? -1] ?? "0",
    };
  });
}

function serializeCsvValue(value) {
  const text = String(value ?? "");
  if (/[",\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function languageChoices(currentValue = "") {
  const choices = [{ value: "*", label: "All Languages (*)" }];
  const seen = new Set(["*"]);
  for (const item of props.languageOptions) {
    const label = String(item?.label || "").trim();
    if (!label || seen.has(label)) continue;
    seen.add(label);
    choices.push({ value: label, label });
  }
  const fallback = String(currentValue || "").trim();
  if (fallback && !seen.has(fallback)) {
    choices.push({ value: fallback, label: `${fallback} (legacy)` });
  }
  return choices;
}

function syncCsv() {
  const columns = ["source_text", "target_language", "target_text", "case_sensitive"];
  const header = columns.join(",");
  const body = rows.value
    .filter((row) => columns.some((col) => String(row[col] ?? "").trim() !== ""))
    .map((row) => columns.map((col) => serializeCsvValue(row[col])).join(","));
  emit("update:modelValue", [header, ...body].join("\n"));
}

function addRow() {
  rows.value.push({ source_text: "", target_language: "*", target_text: "", case_sensitive: "0" });
  syncCsv();
}

function removeRow(index) {
  rows.value.splice(index, 1);
  syncCsv();
}

function loadFromCsv(csv) {
  const parsed = parseTermbaseCsv(csv);
  rows.value = parsed.length > 0 ? parsed : [{ source_text: "", target_language: "*", target_text: "", case_sensitive: "0" }];
}

watch(() => props.modelValue, (newVal) => {
  loadFromCsv(newVal);
});

onMounted(() => {
  loadFromCsv(props.modelValue);
});
</script>
