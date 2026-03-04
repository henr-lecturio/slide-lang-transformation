import { el } from "./dom.js";
import { state } from "./state.js";
import { apiGet, apiPost } from "./api.js";
import { formatRunIdLabel, formatUsd } from "./ui-core.js";
import { openImageModal } from "./modals.js";

const LAB_TEST_SETTINGS_STORAGE_KEY = "slide-transform-lab-test-settings";
const ALLOWED_IMAGE_MODELS = new Set([
  "gemini-3.1-flash-image-preview",
  "gemini-3-pro-image-preview",
  "gemini-2.5-flash-image",
]);
const LAB_SLIDE_STYLE_COLUMNS = [
  { key: "display_key", type: "readonly" },
  { key: "font_weight", type: "select", options: ["Regular", "Medium", "Bold"] },
  { key: "font_size", type: "number", min: "1", step: "1" },
  { key: "min_font_size", type: "number", min: "1", step: "1" },
  { key: "line_spacing_ratio", type: "number", min: "0", step: "0.01" },
  { key: "text_color", type: "text", placeholder: "auto or #RRGGBB" },
  { key: "padding", type: "text", placeholder: "top right bottom left" },
];

let labSlideStyleEditorModel = {
  version: 1,
  defaults: {},
  roles: {},
  slots: {},
};

function parseLabSlideTranslateStylesJson(jsonText) {
  const text = String(jsonText || "").trim();
  if (!text) {
    return { version: 1, defaults: {}, roles: {}, slots: {} };
  }
  try {
    const payload = JSON.parse(text);
    return {
      version: Number(payload?.version) > 0 ? Number(payload.version) : 1,
      defaults: payload && typeof payload.defaults === "object" && payload.defaults ? structuredClone(payload.defaults) : {},
      roles: payload && typeof payload.roles === "object" && payload.roles ? structuredClone(payload.roles) : {},
      slots: payload && typeof payload.slots === "object" && payload.slots ? structuredClone(payload.slots) : {},
    };
  } catch {
    return { version: 1, defaults: {}, roles: {}, slots: {} };
  }
}

function buildLabSlideTranslateStyleRows(model) {
  return [
    { scope_type: "defaults", scope_key: "defaults", display_key: "defaults", style: model.defaults || {} },
    ...Object.entries(model.roles || {}).map(([key, value]) => ({
      scope_type: "role",
      scope_key: key,
      display_key: key,
      style: value || {},
    })),
    ...Object.entries(model.slots || {}).map(([key, value]) => ({
      scope_type: "slot",
      scope_key: key,
      display_key: key,
      style: value || {},
    })),
  ];
}

function displayLabSlideStyleColor(style = {}) {
  const mode = String(style.text_color_mode ?? "").trim();
  const color = String(style.text_color ?? "").trim();
  if (mode === "fixed" && color) return color;
  if (color && color.toLowerCase() !== "auto") return color;
  return "auto";
}

function displayLabSlideStylePadding(style = {}) {
  const padding = String(style.padding ?? "").trim();
  if (padding) return padding;
  const top = style.box_padding_top_ratio ?? style.box_padding_y_ratio;
  const right = style.box_padding_right_ratio ?? style.box_padding_x_ratio;
  const bottom = style.box_padding_bottom_ratio ?? style.box_padding_y_ratio;
  const left = style.box_padding_left_ratio ?? style.box_padding_x_ratio;
  const values = [top, right, bottom, left]
    .map((value) => (value === undefined || value === null || value === "" ? "" : String(value).trim()));
  if (values.every((value) => value !== "")) {
    return values.join(" ");
  }
  return "";
}

function labSlideStyleVisibleValuesFromStyle(style = {}, displayKey = "") {
  const explicitWeight = String(style.font_weight ?? "").trim().toLowerCase();
  let inferredWeight = "Regular";
  if (explicitWeight === "medium") inferredWeight = "Medium";
  else if (explicitWeight === "bold") inferredWeight = "Bold";
  else if (explicitWeight === "regular") inferredWeight = "Regular";
  else {
    const fontPath = String(style.font_path ?? "").toLowerCase();
    if (fontPath.includes("bold")) inferredWeight = "Bold";
    else if (fontPath.includes("medium")) inferredWeight = "Medium";
    else if (fontPath.includes("regular")) inferredWeight = "Regular";
  }
  return {
    display_key: displayKey,
    font_weight: inferredWeight,
    font_size: style.font_size === undefined || style.font_size === null ? "" : String(style.font_size),
    min_font_size: style.min_font_size === undefined || style.min_font_size === null ? "" : String(style.min_font_size),
    line_spacing_ratio: style.line_spacing_ratio === undefined || style.line_spacing_ratio === null ? "" : String(style.line_spacing_ratio),
    text_color: displayLabSlideStyleColor(style),
    padding: displayLabSlideStylePadding(style),
  };
}

function normalizePaddingShorthand(value) {
  const text = String(value ?? "").trim().replace(/,/g, " ");
  if (!text) return "";
  const parts = text.split(/\s+/).filter(Boolean);
  if (parts.length === 0 || parts.length > 4) return text;
  return parts.join(" ");
}

function parseIntegerOrUndefined(value) {
  const text = String(value ?? "").trim();
  if (!text) return undefined;
  const num = Number(text);
  return Number.isFinite(num) ? Math.round(num) : undefined;
}

function parseFloatOrUndefined(value) {
  const text = String(value ?? "").trim();
  if (!text) return undefined;
  const num = Number(text);
  return Number.isFinite(num) ? num : undefined;
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

function syncLabSlideTranslateStylesJsonFromTable() {
  if (!el.labSlideTranslateStylesJson || !el.labSlideTranslateStyleTableBody) return;
  const payload = structuredClone(labSlideStyleEditorModel);
  for (const row of [...el.labSlideTranslateStyleTableBody.querySelectorAll("tr")]) {
    const scopeType = row.dataset.scopeType || "";
    const scopeKey = row.dataset.scopeKey || "";
    const style =
      scopeType === "defaults"
        ? payload.defaults
        : scopeType === "role"
          ? payload.roles?.[scopeKey]
          : payload.slots?.[scopeKey];
    if (!style || typeof style !== "object") continue;

    const current = {};
    for (const column of LAB_SLIDE_STYLE_COLUMNS) {
      if (column.type === "readonly") continue;
      current[column.key] = row.querySelector(`[data-col="${column.key}"]`)?.value ?? "";
    }
    const initial = JSON.parse(row.dataset.initialVisibleValues || "{}");

    if (String(current.font_weight ?? "") !== String(initial.font_weight ?? "")) {
      const weightRaw = String(current.font_weight ?? "").trim().toLowerCase();
      if (["regular", "medium", "bold"].includes(weightRaw)) {
        style.font_weight = weightRaw;
      } else {
        delete style.font_weight;
      }
    }
    if (String(current.font_size ?? "") !== String(initial.font_size ?? "")) {
      const value = parseIntegerOrUndefined(current.font_size);
      if (value === undefined) delete style.font_size;
      else style.font_size = value;
    }
    if (String(current.min_font_size ?? "") !== String(initial.min_font_size ?? "")) {
      const value = parseIntegerOrUndefined(current.min_font_size);
      if (value === undefined) delete style.min_font_size;
      else style.min_font_size = value;
    }
    if (String(current.line_spacing_ratio ?? "") !== String(initial.line_spacing_ratio ?? "")) {
      const value = parseFloatOrUndefined(current.line_spacing_ratio);
      if (value === undefined) delete style.line_spacing_ratio;
      else style.line_spacing_ratio = value;
    }
    if (String(current.text_color ?? "") !== String(initial.text_color ?? "")) {
      const color = String(current.text_color ?? "").trim();
      if (!color || color.toLowerCase() === "auto" || color.toLowerCase() === "inherit") {
        delete style.text_color;
        if (String(style.text_color_mode ?? "").trim() === "fixed") {
          delete style.text_color_mode;
        }
      } else {
        style.text_color = color;
        style.text_color_mode = "fixed";
      }
    }
    if (String(current.padding ?? "") !== String(initial.padding ?? "")) {
      const padding = normalizePaddingShorthand(current.padding);
      deletePaddingKeys(style);
      if (padding) {
        style.padding = padding;
      }
    }
  }
  el.labSlideTranslateStylesJson.value = JSON.stringify(payload, null, 2);
}

function createLabSlideTranslateStyleRow(row) {
  const tr = document.createElement("tr");
  tr.dataset.scopeType = row.scope_type;
  tr.dataset.scopeKey = row.scope_key;
  const visibleValues = labSlideStyleVisibleValuesFromStyle(row.style, row.display_key);
  tr.dataset.initialVisibleValues = JSON.stringify(visibleValues);

  for (const column of LAB_SLIDE_STYLE_COLUMNS) {
    const td = document.createElement("td");
    let control;
    if (column.type === "readonly") {
      control = document.createElement("input");
      control.type = "text";
      control.readOnly = true;
      control.value = String(visibleValues[column.key] ?? "");
    } else if (column.type === "select") {
      control = document.createElement("select");
      for (const optionValue of column.options || []) {
        const option = document.createElement("option");
        option.value = String(optionValue);
        option.textContent = String(optionValue);
        control.appendChild(option);
      }
      control.value = String(visibleValues[column.key] ?? "Regular");
      if (!control.value) {
        control.value = "Regular";
      }
      control.addEventListener("change", syncLabSlideTranslateStylesJsonFromTable);
    } else {
      control = document.createElement("input");
      control.type = column.type;
      if (column.min !== undefined) control.min = column.min;
      if (column.step !== undefined) control.step = column.step;
      if (column.placeholder) control.placeholder = column.placeholder;
      control.value = String(visibleValues[column.key] ?? "");
      control.addEventListener("input", syncLabSlideTranslateStylesJsonFromTable);
      control.addEventListener("change", syncLabSlideTranslateStylesJsonFromTable);
    }
    control.dataset.col = column.key;
    td.appendChild(control);
    tr.appendChild(td);
  }
  return tr;
}

function renderLabSlideTranslateStyleEditor(jsonText) {
  if (!el.labSlideTranslateStyleTableBody || !el.labSlideTranslateStylesJson) return;
  labSlideStyleEditorModel = parseLabSlideTranslateStylesJson(jsonText);
  el.labSlideTranslateStylesJson.value = String(jsonText || "").trim();
  el.labSlideTranslateStyleTableBody.innerHTML = "";
  for (const row of buildLabSlideTranslateStyleRows(labSlideStyleEditorModel)) {
    el.labSlideTranslateStyleTableBody.appendChild(createLabSlideTranslateStyleRow(row));
  }
  syncLabSlideTranslateStylesJsonFromTable();
}

function setLabSlideTranslateStyleEditorDisabled(disabled) {
  if (el.labSlideTranslateStyleEditorToggle) {
    el.labSlideTranslateStyleEditorToggle.disabled = disabled;
  }
  if (el.labSlideTranslateStyleTableBody) {
    for (const input of el.labSlideTranslateStyleTableBody.querySelectorAll("input, select")) {
      input.disabled = disabled;
    }
  }
}

export function toggleLabSlideTranslateStyleEditor() {
  if (!el.labSlideTranslateStyleEditorPanel || !el.labSlideTranslateStyleEditorToggle || !el.labSlideTranslateStyleEditorBody) return;
  const nextOpen = !el.labSlideTranslateStyleEditorPanel.classList.contains("is-open");
  el.labSlideTranslateStyleEditorPanel.classList.toggle("is-open", nextOpen);
  el.labSlideTranslateStyleEditorToggle.setAttribute("aria-expanded", nextOpen ? "true" : "false");
  el.labSlideTranslateStyleEditorBody.hidden = !nextOpen;
}

function setNodeText(node, text) {
  if (node) node.textContent = text;
}

function formatLabSelectionMeta(runId, eventId) {
  const rawRunId = String(runId || "").trim();
  const tsMatch = rawRunId.match(/^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}(?:-\d{2})?)/);
  const runLabel = formatRunIdLabel(tsMatch ? tsMatch[1] : rawRunId || "-");
  const eventNr = Number(eventId);
  const eventLabel = Number.isFinite(eventNr) && eventNr > 0 ? String(eventNr) : "-";
  return `| selected: ${runLabel}, event ${eventLabel}`;
}

function formatLabStatus(status, hasSelection) {
  if (!hasSelection) {
    return { label: "No image selected", iconClass: "", lineClass: "is-idle" };
  }
  switch (status) {
    case "running":
      return { label: "Running", iconClass: "is-running", lineClass: "is-running" };
    case "stopping":
      return { label: "Stopping", iconClass: "is-running", lineClass: "is-running" };
    case "done":
      return { label: "Done", iconClass: "is-done", lineClass: "is-done" };
    case "error":
      return { label: "Error", iconClass: "is-error", lineClass: "is-error" };
    case "stopped":
      return { label: "Stopped", iconClass: "is-stopped", lineClass: "is-stopped" };
    default:
      return { label: "Ready", iconClass: "", lineClass: "is-ready" };
  }
}

function renderLabStatusLine(status) {
  if (!el.labJobStatus) return;
  const meta = formatLabStatus(status, Boolean(state.labSelectedImage?.image_url));
  el.labJobStatus.className = `export-lab-status-line lab-toolbar-status ${meta.lineClass}`;
  el.labJobStatus.innerHTML = "";
  const chip = document.createElement("div");
  chip.className = "export-lab-status-chip";
  const icon = document.createElement("span");
  icon.className = meta.iconClass ? `step-icon ${meta.iconClass}` : "step-icon";
  icon.setAttribute("aria-hidden", "true");
  const label = document.createElement("span");
  label.className = "export-lab-status-label";
  label.textContent = meta.label;
  chip.append(icon, label);
  el.labJobStatus.appendChild(chip);
}

function readLabSettingsFromStorage() {
  try {
    const raw = localStorage.getItem(LAB_TEST_SETTINGS_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function persistLabTestSettings() {
  try {
    localStorage.setItem(LAB_TEST_SETTINGS_STORAGE_KEY, JSON.stringify(state.labTestSettings || {}));
  } catch {
    // ignore storage failures
  }
}

function selectedMainTargetLanguageLabel() {
  const code = String(el.finalSlideTargetLanguage?.value || "").trim();
  if (!code) return "";
  const option = (Array.isArray(state.ttsLanguageOptions) ? state.ttsLanguageOptions : [])
    .find((item) => item.tts_language_code === code);
  return String(option?.label || "").trim();
}

function defaultLabTestSettingsFromCurrentUi() {
  return {
    slide_edit_model: el.geminiEditModel.value.trim(),
    slide_edit_prompt: el.geminiEditPrompt.value,
    target_language: selectedMainTargetLanguageLabel(),
    slide_translate_model: el.geminiTranslateModel.value.trim(),
    slide_translate_prompt: el.geminiTranslatePrompt.value,
    slide_translate_styles_json: String(el.slideTranslateStylesJson?.value || "").trim(),
    slide_upscale_mode: el.finalSlideUpscaleMode.value.trim() || "swin2sr",
    slide_upscale_model: el.finalSlideUpscaleModel.value.trim(),
    slide_upscale_device: el.finalSlideUpscaleDevice.value.trim() || "auto",
    slide_upscale_tile_size: Number(el.finalSlideUpscaleTileSize.value || 256),
    slide_upscale_tile_overlap: Number(el.finalSlideUpscaleTileOverlap.value || 24),
    replicate_model_ref: el.replicateNightmareRealesrganModelRef.value.trim(),
    replicate_version_id: el.replicateNightmareRealesrganVersionId.value.trim(),
  };
}

function normalizeLabTestSettings(raw = {}) {
  const fallback = defaultLabTestSettingsFromCurrentUi();
  const next = {
    slide_edit_model: String(raw.slide_edit_model || fallback.slide_edit_model || "gemini-3-pro-image-preview").trim(),
    slide_edit_prompt: String(raw.slide_edit_prompt ?? fallback.slide_edit_prompt ?? ""),
    target_language: String(raw.target_language || fallback.target_language || "").trim(),
    slide_translate_model: String(raw.slide_translate_model || fallback.slide_translate_model || "gemini-3-pro-image-preview").trim(),
    slide_translate_prompt: String(raw.slide_translate_prompt ?? fallback.slide_translate_prompt ?? ""),
    slide_translate_styles_json: String(raw.slide_translate_styles_json ?? fallback.slide_translate_styles_json ?? "").trim(),
    slide_upscale_mode: String(raw.slide_upscale_mode || fallback.slide_upscale_mode || "swin2sr").trim(),
    slide_upscale_model: String(raw.slide_upscale_model || fallback.slide_upscale_model || "caidas/swin2SR-classical-sr-x4-64").trim(),
    slide_upscale_device: String(raw.slide_upscale_device || fallback.slide_upscale_device || "auto").trim(),
    slide_upscale_tile_size: Number(raw.slide_upscale_tile_size ?? fallback.slide_upscale_tile_size ?? 256),
    slide_upscale_tile_overlap: Number(raw.slide_upscale_tile_overlap ?? fallback.slide_upscale_tile_overlap ?? 24),
    replicate_model_ref: String(raw.replicate_model_ref || fallback.replicate_model_ref || "nightmareai/real-esrgan").trim(),
    replicate_version_id: String(raw.replicate_version_id || fallback.replicate_version_id || "f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa").trim(),
  };
  if (!ALLOWED_IMAGE_MODELS.has(next.slide_edit_model)) {
    next.slide_edit_model = "gemini-3-pro-image-preview";
  }
  if (!ALLOWED_IMAGE_MODELS.has(next.slide_translate_model)) {
    next.slide_translate_model = "gemini-3-pro-image-preview";
  }
  if (!["swin2sr", "replicate_nightmare_realesrgan"].includes(next.slide_upscale_mode)) {
    next.slide_upscale_mode = "swin2sr";
  }
  if (!Number.isFinite(next.slide_upscale_tile_size) || next.slide_upscale_tile_size < 0) {
    next.slide_upscale_tile_size = 256;
  }
  if (!Number.isFinite(next.slide_upscale_tile_overlap) || next.slide_upscale_tile_overlap < 0) {
    next.slide_upscale_tile_overlap = 24;
  }
  return next;
}

function ensureLabTestSettings() {
  if (state.labTestSettings) return state.labTestSettings;
  state.labTestSettings = normalizeLabTestSettings(readLabSettingsFromStorage() || defaultLabTestSettingsFromCurrentUi());
  persistLabTestSettings();
  return state.labTestSettings;
}

function renderLabTargetLanguageOptions() {
  const selectedLabel = String(state.labTestSettings?.target_language || "").trim();
  el.labFinalSlideTargetLanguage.innerHTML = "";
  const options = Array.isArray(state.ttsLanguageOptions) ? state.ttsLanguageOptions : [];
  if (options.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No languages available";
    el.labFinalSlideTargetLanguage.appendChild(option);
    return;
  }
  for (const item of options) {
    const option = document.createElement("option");
    option.value = item.label;
    option.textContent = item.launch_readiness
      ? `${item.label} [${item.tts_language_code}] (${item.launch_readiness})`
      : `${item.label} [${item.tts_language_code}]`;
    el.labFinalSlideTargetLanguage.appendChild(option);
  }
  const preferred = options.find((item) => item.label === selectedLabel) || options[0];
  el.labFinalSlideTargetLanguage.value = preferred.label;
}

export function syncLabSettingsFieldState() {
  const mode = el.labFinalSlideUpscaleMode.value;
  const translateMode = String(el.finalSlideTranslationMode?.value || "gemini").trim().toLowerCase();
  const localRows = document.querySelectorAll(".lab-upscale-local-row");
  const replicateRows = document.querySelectorAll(".lab-upscale-replicate-row");
  const isLocal = mode === "swin2sr";
  for (const row of localRows) row.hidden = !isLocal;
  for (const row of replicateRows) row.hidden = isLocal;
  const deterministicSlideTranslate = translateMode === "deterministic_glossary";
  const geminiTranslateMode = translateMode !== "deterministic_glossary";
  if (el.labGeminiTranslateModel) {
    el.labGeminiTranslateModel.disabled = !geminiTranslateMode;
  }
  if (el.labGeminiTranslatePrompt) {
    el.labGeminiTranslatePrompt.disabled = !geminiTranslateMode;
  }
  setLabSlideTranslateStyleEditorDisabled(!deterministicSlideTranslate);
}

function applyLabTestSettingsToForm() {
  ensureLabTestSettings();
  el.labGeminiEditModel.value = state.labTestSettings.slide_edit_model;
  el.labGeminiEditPrompt.value = state.labTestSettings.slide_edit_prompt;
  renderLabTargetLanguageOptions();
  el.labGeminiTranslateModel.value = state.labTestSettings.slide_translate_model;
  el.labGeminiTranslatePrompt.value = state.labTestSettings.slide_translate_prompt;
  renderLabSlideTranslateStyleEditor(state.labTestSettings.slide_translate_styles_json);
  el.labFinalSlideUpscaleMode.value = state.labTestSettings.slide_upscale_mode;
  el.labFinalSlideUpscaleModel.value = state.labTestSettings.slide_upscale_model;
  el.labFinalSlideUpscaleDevice.value = state.labTestSettings.slide_upscale_device;
  el.labFinalSlideUpscaleTileSize.value = state.labTestSettings.slide_upscale_tile_size;
  el.labFinalSlideUpscaleTileOverlap.value = state.labTestSettings.slide_upscale_tile_overlap;
  el.labReplicateNightmareRealesrganModelRef.value = state.labTestSettings.replicate_model_ref;
  el.labReplicateNightmareRealesrganVersionId.value = state.labTestSettings.replicate_version_id;
  syncLabSettingsFieldState();
}

function readLabTestSettingsFromForm() {
  syncLabSlideTranslateStylesJsonFromTable();
  state.labTestSettings = normalizeLabTestSettings({
    slide_edit_model: el.labGeminiEditModel.value,
    slide_edit_prompt: el.labGeminiEditPrompt.value,
    target_language: el.labFinalSlideTargetLanguage.value,
    slide_translate_model: el.labGeminiTranslateModel.value,
    slide_translate_prompt: el.labGeminiTranslatePrompt.value,
    slide_translate_styles_json: el.labSlideTranslateStylesJson?.value || "",
    slide_upscale_mode: el.labFinalSlideUpscaleMode.value,
    slide_upscale_model: el.labFinalSlideUpscaleModel.value,
    slide_upscale_device: el.labFinalSlideUpscaleDevice.value,
    slide_upscale_tile_size: el.labFinalSlideUpscaleTileSize.value,
    slide_upscale_tile_overlap: el.labFinalSlideUpscaleTileOverlap.value,
    replicate_model_ref: el.labReplicateNightmareRealesrganModelRef.value,
    replicate_version_id: el.labReplicateNightmareRealesrganVersionId.value,
  });
  persistLabTestSettings();
  return state.labTestSettings;
}

function buildLabSettingsSummary() {
  const settings = ensureLabTestSettings();
  return [
    `edit=${settings.slide_edit_model || "-"}`,
    `translate=${settings.target_language || "-"} [${String(el.finalSlideTranslationMode?.value || "gemini").trim() || "gemini"}]`,
    `upscale=${settings.slide_upscale_mode || "-"}`,
  ].join(" | ");
}

export function syncLabTestSections() {
  const sections = document.querySelectorAll(".step-section[data-lab-step-section]");
  for (const section of sections) {
    const sectionId = section.dataset.labStepSection;
    const body = section.querySelector(".step-section-body");
    const toggleBtn = section.querySelector(".lab-step-section-toggle");
    if (!sectionId) continue;
    if (!(sectionId in state.labStepSectionExpanded)) {
      state.labStepSectionExpanded[sectionId] = false;
    }
    const expanded = Boolean(state.labStepSectionExpanded[sectionId]);
    section.classList.toggle("is-open", expanded);
    if (body) {
      body.hidden = !expanded;
      body.setAttribute("aria-hidden", expanded ? "false" : "true");
    }
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", expanded ? "true" : "false");
      toggleBtn.setAttribute("aria-label", expanded ? "Collapse test settings section" : "Expand test settings section");
    }
  }
}

export function initializeLabTestSettings() {
  ensureLabTestSettings();
  applyLabTestSettingsToForm();
  syncLabTestSections();
  if (state.labStatus === "idle") {
    setNodeText(el.labJobMeta, `Test settings: ${buildLabSettingsSummary()}`);
  }
}

export function resetLabTestSettingsFromCurrentSettings() {
  state.labTestSettings = normalizeLabTestSettings(defaultLabTestSettingsFromCurrentUi());
  persistLabTestSettings();
  applyLabTestSettingsToForm();
  syncLabTestSections();
  if (state.labStatus === "idle") {
    setNodeText(el.labJobMeta, `Test settings: ${buildLabSettingsSummary()}`);
  }
}

export function saveLabTestSettings() {
  readLabTestSettingsFromForm();
  applyLabTestSettingsToForm();
  syncLabTestSections();
  if (state.labStatus === "idle") {
    setNodeText(el.labJobMeta, `Test settings: ${buildLabSettingsSummary()}`);
  }
}

export function syncLabActionState() {
  const hasImage = Boolean(state.labSelectedImage && state.labSelectedImage.image_url);
  const isBusy = state.labStatus === "running" || state.labStatus === "stopping";
  el.labPickImage.disabled = isBusy;
  el.labOpenSettings.disabled = isBusy;
  el.labRunEdit.disabled = isBusy || !hasImage;
  el.labRunTranslate.disabled = isBusy || !hasImage;
  el.labRunUpscale.disabled = isBusy || !hasImage;
  if (el.labStopRun) {
    el.labStopRun.disabled = state.labStatus !== "running";
    el.labStopRun.textContent = state.labStatus === "stopping" ? "Stopping..." : "Stop Execution";
  }
}

export function renderLabSelection() {
  const item = state.labSelectedImage;
  if (!item) {
    setNodeText(el.labSelectedImage, "");
    el.labOriginalImage.removeAttribute("src");
    el.labOriginalImage.onclick = null;
    renderLabStatusLine(state.labStatus || "idle");
    syncLabActionState();
    return;
  }
  setNodeText(el.labSelectedImage, formatLabSelectionMeta(item.run_id, item.event_id));
  el.labOriginalImage.src = `${item.image_url}?v=${Date.now()}`;
  el.labOriginalImage.onclick = () => openImageModal(item.image_url, item.name || `event_${item.event_id}`);
  renderLabStatusLine(state.labStatus || "idle");
  syncLabActionState();
}

export function setLabStatus(current) {
  const status = current?.status || "idle";
  state.labStatus = status;
  renderLabStatusLine(status);
  const resultMeta = [];
  if (current?.message) resultMeta.push(current.message);
  if (current?.input_name) resultMeta.push(`input=${current.input_name}`);
  if (current?.result_name) resultMeta.push(`result=${current.result_name}`);
  if (current?.estimated_cost_usd) resultMeta.push(`est_cost=${formatUsd(current.estimated_cost_usd)}`);
  setNodeText(
    el.labJobMeta,
    resultMeta.length > 0 ? resultMeta.join(" | ") : `Test settings: ${buildLabSettingsSummary()}`,
  );
  const logs = (current?.log_tail || []).slice(-120);
  const nextLog = logs.join("\n");
  if (el.labLog.textContent !== nextLog) {
    el.labLog.textContent = nextLog;
    el.labLog.scrollTop = el.labLog.scrollHeight;
  }
  if (current?.result_url) {
    el.labResultImage.src = `${current.result_url}?v=${Date.now()}`;
    el.labResultImage.onclick = () => openImageModal(current.result_url, current.result_name || "lab-result");
  } else {
    el.labResultImage.removeAttribute("src");
    el.labResultImage.onclick = null;
  }
  if (!state.labSelectedImage && current?.original_url) {
    setNodeText(el.labSelectedImage, formatLabSelectionMeta(current.run_id, current.event_id));
    el.labOriginalImage.src = `${current.original_url}?v=${Date.now()}`;
    el.labOriginalImage.onclick = () => openImageModal(current.original_url, current.input_name || "lab-input");
  }
  syncLabActionState();
}

export async function loadLabStatus() {
  const current = await apiGet("/api/lab/status");
  setLabStatus(current);
}

export async function stopLabJob() {
  const res = await apiPost("/api/lab/stop", {});
  setLabStatus(res.current || {});
}

export async function runLabAction(action) {
  if (!state.labSelectedImage) {
    throw new Error("Bitte zuerst ein Bild im Image Lab wählen.");
  }
  el.labResultImage.removeAttribute("src");
  el.labResultImage.onclick = null;
  const payload = {
    run_id: state.labSelectedImage.run_id,
    event_id: state.labSelectedImage.event_id,
    settings: readLabTestSettingsFromForm(),
  };
  const res = await apiPost(`/api/lab/${action}`, payload);
  setLabStatus(res.current || {});
}
