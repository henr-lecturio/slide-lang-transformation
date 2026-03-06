import { el } from "./dom.js";
import { state } from "./state.js";
import { apiGet, apiPost } from "./api.js";
import { videoThumbUrl } from "./ui-core.js";
import { clearHealthStatus, setHealthStatus } from "./health-checks.js";
import {
  getSelectedTtsLanguageOption,
  listTtsLanguageOptions,
  renderTtsLanguageOptions,
  updateTtsLanguageHint,
} from "./tts-language.js";

const TERMBASE_COLUMNS = [
  { key: "source_text", label: "Source Text" },
  { key: "target_language", label: "Target Language" },
  { key: "target_text", label: "Target Text" },
  { key: "case_sensitive", label: "Case Sensitive" },
];

const SLIDE_STYLE_COLUMNS = [
  { key: "display_key", label: "Key", type: "readonly" },
  { key: "font_weight", label: "Weight", type: "select", options: ["Regular", "Medium", "Bold"] },
  { key: "font_size", label: "Font Size", type: "number", min: "1", step: "1" },
  { key: "min_font_size", label: "Min Font", type: "number", min: "1", step: "1" },
  { key: "line_spacing_ratio", label: "Line Spacing", type: "number", min: "0", step: "0.01" },
  { key: "text_color", label: "Color", type: "text", placeholder: "auto or #RRGGBB" },
  { key: "padding", label: "Padding", type: "text", placeholder: "top right bottom left" },
];

let slideTranslateStyleEditorModel = {
  version: 1,
  defaults: {},
  roles: {},
  slots: {},
};
let lastLoadedConfig = {};

function isStepSectionEnabled(section) {
  const inputId = section?.dataset?.stepInput || "";
  if (!inputId) return true;
  const input = document.getElementById(inputId);
  return Boolean(input && input.checked);
}

export function syncStepSections() {
  const sections = document.querySelectorAll(".step-section[data-step-section]");
  for (const section of sections) {
    const sectionId = section.dataset.stepSection;
    const body = section.querySelector(".step-section-body");
    const toggleBtn = section.querySelector(".step-section-toggle");
    const forced = !section.dataset.stepInput;
    const enabled = isStepSectionEnabled(section);

    if (!(sectionId in state.stepSectionExpanded)) {
      state.stepSectionExpanded[sectionId] = false;
    }

    if (!forced && !enabled) {
      state.stepSectionExpanded[sectionId] = false;
    }

    const expanded = Boolean(state.stepSectionExpanded[sectionId]);
    const showBody = forced ? expanded : enabled && expanded;

    section.classList.toggle("is-forced", forced);
    section.classList.toggle("is-enabled", enabled);
    section.classList.toggle("is-disabled", !enabled);
    section.classList.toggle("is-open", showBody);

    if (body) {
      body.hidden = !showBody;
      body.setAttribute("aria-hidden", showBody ? "false" : "true");
    }

    if (toggleBtn) {
      toggleBtn.disabled = !forced && !enabled;
      toggleBtn.setAttribute("aria-expanded", showBody ? "true" : "false");
      toggleBtn.setAttribute("aria-label", !forced && !enabled ? "Section disabled" : (showBody ? "Collapse settings section" : "Expand settings section"));
    }
  }
}

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
  if (!text) {
    return [];
  }
  const lines = text.split("\n").filter(Boolean);
  if (lines.length === 0) {
    return [];
  }
  const header = parseCsvLine(lines[0]).map((value) => value.trim());
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

function buildTermbaseLanguageChoices(currentValue = "") {
  const choices = [{ value: "*", label: "All Languages (*)" }];
  const seen = new Set(["*"]);
  for (const item of Array.isArray(state.ttsLanguageOptions) ? state.ttsLanguageOptions : []) {
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

function serializeCsvValue(value) {
  const text = String(value ?? "");
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function syncTermbaseCsvFromTable() {
  if (!el.translationTermbaseCsv || !el.termbaseTableBody) return;
  const rows = [...el.termbaseTableBody.querySelectorAll("tr")].map((row) => ({
    source_text: row.querySelector('[data-col="source_text"]')?.value ?? "",
    target_language: row.querySelector('[data-col="target_language"]')?.value ?? "",
    target_text: row.querySelector('[data-col="target_text"]')?.value ?? "",
    case_sensitive: row.querySelector('[data-col="case_sensitive"]')?.value ?? "0",
  }));
  const header = TERMBASE_COLUMNS.map((column) => column.key).join(",");
  const body = rows
    .filter((row) => TERMBASE_COLUMNS.some((column) => String(row[column.key] ?? "").trim() !== ""))
    .map((row) => TERMBASE_COLUMNS.map((column) => serializeCsvValue(row[column.key])).join(","));
  el.translationTermbaseCsv.value = [header, ...body].join("\n");
}

function parseSlideTranslateStylesJson(jsonText) {
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

function buildSlideTranslateStyleRows(model) {
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

function displaySlideStyleColor(style = {}) {
  const mode = String(style.text_color_mode ?? "").trim();
  const color = String(style.text_color ?? "").trim();
  if (mode === "fixed" && color) return color;
  if (color && color.toLowerCase() !== "auto") return color;
  return "auto";
}

function displaySlideStylePadding(style = {}) {
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

function slideStyleVisibleValuesFromStyle(style = {}, displayKey = "") {
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
    text_color: displaySlideStyleColor(style),
    padding: displaySlideStylePadding(style),
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

function syncSlideTranslateStylesJsonFromTable() {
  if (!el.slideTranslateStylesJson || !el.slideTranslateStyleTableBody) return;
  const payload = structuredClone(slideTranslateStyleEditorModel);
  for (const row of [...el.slideTranslateStyleTableBody.querySelectorAll("tr")]) {
    const scopeType = row.dataset.scopeType || "";
    const scopeKey = row.dataset.scopeKey || "";
    const style =
      scopeType === "defaults"
        ? payload.defaults
        : scopeType === "role"
          ? payload.roles?.[scopeKey]
          : payload.slots?.[scopeKey];
    if (!style || typeof style !== "object") continue;
    style.font_size_mode = "fixed";

    const current = {};
    for (const column of SLIDE_STYLE_COLUMNS) {
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
  el.slideTranslateStylesJson.value = JSON.stringify(payload, null, 2);
}

function createSlideTranslateStyleRow(row) {
  const tr = document.createElement("tr");
  tr.dataset.scopeType = row.scope_type;
  tr.dataset.scopeKey = row.scope_key;
  const visibleValues = slideStyleVisibleValuesFromStyle(row.style, row.display_key);
  tr.dataset.initialVisibleValues = JSON.stringify(visibleValues);

  for (const column of SLIDE_STYLE_COLUMNS) {
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
      control.addEventListener("change", syncSlideTranslateStylesJsonFromTable);
    } else {
      control = document.createElement("input");
      control.type = column.type;
      if (column.min !== undefined) control.min = column.min;
      if (column.step !== undefined) control.step = column.step;
      if (column.placeholder) control.placeholder = column.placeholder;
      control.value = String(visibleValues[column.key] ?? "");
      control.addEventListener("input", syncSlideTranslateStylesJsonFromTable);
      control.addEventListener("change", syncSlideTranslateStylesJsonFromTable);
    }
    control.dataset.col = column.key;
    td.appendChild(control);
    tr.appendChild(td);
  }
  return tr;
}

export function renderSlideTranslateStyleEditor(jsonText) {
  if (!el.slideTranslateStyleTableBody || !el.slideTranslateStylesJson) return;
  slideTranslateStyleEditorModel = parseSlideTranslateStylesJson(jsonText);
  el.slideTranslateStylesJson.value = String(jsonText || "").trim();
  el.slideTranslateStyleTableBody.innerHTML = "";
  for (const row of buildSlideTranslateStyleRows(slideTranslateStyleEditorModel)) {
    el.slideTranslateStyleTableBody.appendChild(createSlideTranslateStyleRow(row));
  }
  syncSlideTranslateStylesJsonFromTable();
}

export function toggleSlideTranslateStyleEditor() {
  if (!el.slideTranslateStyleEditorPanel || !el.slideTranslateStyleEditorToggle || !el.slideTranslateStyleEditorBody) return;
  const nextOpen = !el.slideTranslateStyleEditorPanel.classList.contains("is-open");
  el.slideTranslateStyleEditorPanel.classList.toggle("is-open", nextOpen);
  el.slideTranslateStyleEditorToggle.setAttribute("aria-expanded", nextOpen ? "true" : "false");
  el.slideTranslateStyleEditorBody.hidden = !nextOpen;
}

function setSlideTranslateStyleEditorDisabled(disabled) {
  if (el.slideTranslateStyleEditorToggle) el.slideTranslateStyleEditorToggle.disabled = disabled;
  if (el.slideTranslateStyleTableBody) {
    for (const input of el.slideTranslateStyleTableBody.querySelectorAll("input, select")) {
      input.disabled = disabled;
    }
  }
}

function createTermbaseRow(row = {}) {
  const tr = document.createElement("tr");
  for (const column of TERMBASE_COLUMNS) {
    const td = document.createElement("td");
    if (column.key === "target_language") {
      const select = document.createElement("select");
      select.dataset.col = column.key;
      const currentValue = String(row[column.key] ?? "").trim();
      for (const choice of buildTermbaseLanguageChoices(currentValue)) {
        const option = document.createElement("option");
        option.value = choice.value;
        option.textContent = choice.label;
        select.appendChild(option);
      }
      select.value = currentValue || "*";
      if (!select.value) {
        select.value = "*";
      }
      select.addEventListener("change", syncTermbaseCsvFromTable);
      td.appendChild(select);
    } else if (column.key === "case_sensitive") {
      const select = document.createElement("select");
      select.dataset.col = column.key;
      for (const value of ["0", "1"]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value === "1" ? "Yes" : "No";
        select.appendChild(option);
      }
      select.value = String(row[column.key] ?? "0").trim() === "1" ? "1" : "0";
      select.addEventListener("change", syncTermbaseCsvFromTable);
      td.appendChild(select);
    } else {
      const input = document.createElement("input");
      input.type = "text";
      input.dataset.col = column.key;
      input.value = String(row[column.key] ?? "");
      input.addEventListener("input", syncTermbaseCsvFromTable);
      td.appendChild(input);
    }
    tr.appendChild(td);
  }
  const actions = document.createElement("td");
  actions.className = "termbase-table-actions";
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "termbase-remove-row";
  remove.textContent = "Remove";
  remove.addEventListener("click", () => {
    tr.remove();
    syncTermbaseCsvFromTable();
  });
  actions.appendChild(remove);
  tr.appendChild(actions);
  return tr;
}

export function renderTermbaseEditor(csvText) {
  if (!el.termbaseTableBody || !el.translationTermbaseCsv) return;
  el.translationTermbaseCsv.value = String(csvText || "");
  el.termbaseTableBody.innerHTML = "";
  const rows = parseTermbaseCsv(csvText);
  for (const row of rows) {
    el.termbaseTableBody.appendChild(createTermbaseRow(row));
  }
  if (rows.length === 0) {
    el.termbaseTableBody.appendChild(createTermbaseRow());
  }
  syncTermbaseCsvFromTable();
}

export function toggleTermbaseEditor() {
  if (!el.termbaseEditorPanel || !el.termbaseEditorToggle || !el.termbaseEditorBody) return;
  const nextOpen = !el.termbaseEditorPanel.classList.contains("is-open");
  el.termbaseEditorPanel.classList.toggle("is-open", nextOpen);
  el.termbaseEditorToggle.setAttribute("aria-expanded", nextOpen ? "true" : "false");
  el.termbaseEditorBody.hidden = !nextOpen;
}

export function addTermbaseRow() {
  if (!el.termbaseTableBody) return;
  el.termbaseTableBody.appendChild(createTermbaseRow());
  syncTermbaseCsvFromTable();
}

export function renderSelectedVideo(syncActionState = () => {}) {
  const path = state.selectedVideoPath || "";
  el.selectedVideoPath.textContent = path ? `VIDEO_PATH: ${path}` : "VIDEO_PATH: (nicht gesetzt)";
  if (!path) {
    el.selectedVideoThumb.removeAttribute("src");
    syncActionState();
    return;
  }
  el.selectedVideoThumb.src = videoThumbUrl(path);
  syncActionState();
}

function renderHomeQuickLanguageOptions(preferredCode = "", preferredLabel = "") {
  if (!el.homeTargetLanguage) return;
  const previousCode = String(preferredCode || el.homeTargetLanguage.value || "").trim();
  const previousLabel = String(preferredLabel || "").trim();
  el.homeTargetLanguage.innerHTML = "";
  const options = listTtsLanguageOptions();
  if (options.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No languages";
    el.homeTargetLanguage.appendChild(option);
    el.homeTargetLanguage.value = "";
    return;
  }
  for (const item of options) {
    const option = document.createElement("option");
    option.value = item.tts_language_code;
    option.textContent = item.label || item.tts_language_code;
    el.homeTargetLanguage.appendChild(option);
  }
  const preferred = options.find((item) => item.tts_language_code === previousCode)
    || options.find((item) => item.label === previousLabel)
    || options[0];
  el.homeTargetLanguage.value = preferred.tts_language_code;
}

export function setConfig(cfg, { syncActionState = () => {} } = {}) {
  lastLoadedConfig = { ...(cfg || {}) };
  state.selectedVideoPath = cfg.VIDEO_PATH || "";
  el.roiX0.value = cfg.ROI_X0;
  el.roiY0.value = cfg.ROI_Y0;
  el.roiX1.value = cfg.ROI_X1;
  el.roiY1.value = cfg.ROI_Y1;
  el.runStepEdit.checked = Boolean(cfg.RUN_STEP_EDIT);
  el.runStepTranslate.checked = Boolean(cfg.RUN_STEP_TRANSLATE);
  el.runStepUpscale.checked = Boolean(cfg.RUN_STEP_UPSCALE);
  el.runStepTextTranslate.checked = Boolean(cfg.RUN_STEP_TEXT_TRANSLATE);
  el.runStepTts.checked = Boolean(cfg.RUN_STEP_TTS);
  el.runStepVideoExport.checked = Boolean(cfg.RUN_STEP_VIDEO_EXPORT);
  el.finalSourceModeAuto.value = cfg.FINAL_SOURCE_MODE_AUTO || "auto";
  el.transcriptionProvider.value = cfg.TRANSCRIPTION_PROVIDER || "whisper";
  if (el.homeTranscriptionProvider) {
    el.homeTranscriptionProvider.value = cfg.TRANSCRIPTION_PROVIDER || "whisper";
  }
  el.whisperModel.value = cfg.WHISPER_MODEL || "medium";
  el.whisperDevice.value = cfg.WHISPER_DEVICE || "cuda";
  el.whisperComputeType.value = cfg.WHISPER_COMPUTE_TYPE || "float16";
  el.whisperLanguage.value = cfg.WHISPER_LANGUAGE || "";
  el.googleSpeechProjectId.value = cfg.GOOGLE_SPEECH_PROJECT_ID || "";
  el.googleSpeechLocation.value = cfg.GOOGLE_SPEECH_LOCATION || "global";
  el.googleSpeechModel.value = cfg.GOOGLE_SPEECH_MODEL || "chirp_3";
  el.googleSpeechLanguageCodes.value = cfg.GOOGLE_SPEECH_LANGUAGE_CODES || "en-US";
  el.googleSpeechChunkSec.value = cfg.GOOGLE_SPEECH_CHUNK_SEC ?? 55;
  el.googleSpeechChunkOverlapSec.value = cfg.GOOGLE_SPEECH_CHUNK_OVERLAP_SEC ?? 0.75;
  el.fullslideSampleFrames.value = cfg.FULLSLIDE_SAMPLE_FRAMES ?? 3;
  el.fullslideBorderStripPx.value = cfg.FULLSLIDE_BORDER_STRIP_PX ?? 24;
  el.fullslideMinMatchedSides.value = cfg.FULLSLIDE_MIN_MATCHED_SIDES ?? 2;
  el.fullslideBorderDiffThreshold.value = cfg.FULLSLIDE_BORDER_DIFF_THRESHOLD ?? 16.0;
  el.fullslidePersonBoxAreaRatio.value = cfg.FULLSLIDE_PERSON_BOX_AREA_RATIO ?? 0.02;
  el.fullslidePersonOutsideRatio.value = cfg.FULLSLIDE_PERSON_OUTSIDE_RATIO ?? 0.35;
  el.keyframeSettleFrames.value = cfg.KEYFRAME_SETTLE_FRAMES;
  el.keyframeStableEndGuardFrames.value = cfg.KEYFRAME_STABLE_END_GUARD_FRAMES;
  el.keyframeStableLookaheadFrames.value = cfg.KEYFRAME_STABLE_LOOKAHEAD_FRAMES;
  el.speakerFilterMinStage1VideoRatio.value = cfg.SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO;
  el.speakerFilterMaxEdgeDensity.value = cfg.SPEAKER_FILTER_MAX_EDGE_DENSITY;
  el.speakerFilterMaxLaplacianVar.value = cfg.SPEAKER_FILTER_MAX_LAPLACIAN_VAR;
  el.speakerFilterMaxDurationSec.value = cfg.SPEAKER_FILTER_MAX_DURATION_SEC;
  el.finalSlidePostprocessMode.value = cfg.FINAL_SLIDE_POSTPROCESS_MODE || "local";
  el.geminiEditModel.value = cfg.GEMINI_EDIT_MODEL || "gemini-3-pro-image-preview";
  el.geminiEditPrompt.value = cfg.GEMINI_EDIT_PROMPT || "";
  el.finalSlideTranslationMode.value = cfg.FINAL_SLIDE_TRANSLATION_MODE || "none";
  state.ttsLanguageOptions = Array.isArray(cfg.GEMINI_TTS_LANGUAGE_OPTIONS) ? cfg.GEMINI_TTS_LANGUAGE_OPTIONS : [];
  if (el.finalSlideTargetLanguageSearch) {
    el.finalSlideTargetLanguageSearch.value = "";
  }
  renderTtsLanguageOptions("", cfg.GOOGLE_TTS_LANGUAGE_CODE || "", cfg.FINAL_SLIDE_TARGET_LANGUAGE || "");
  renderHomeQuickLanguageOptions(cfg.GOOGLE_TTS_LANGUAGE_CODE || "", cfg.FINAL_SLIDE_TARGET_LANGUAGE || "");
  el.geminiTranslateModel.value = cfg.GEMINI_TRANSLATE_MODEL || "gemini-3-pro-image-preview";
  el.geminiTranslateMaxReviewRetries.value = cfg.SLIDE_TRANSLATE_MAX_REVIEW_RETRIES ?? 3;
  el.geminiTranslatePrompt.value = cfg.GEMINI_TRANSLATE_PROMPT || "";
  el.slideTranslateVisionProjectId.value = cfg.GCLOUD_VISION_PROJECTID
    || cfg.GOOGLE_VISION_PROJECT_ID
    || cfg.GCLOUD_TRANSLATE_PROJECTID
    || cfg.GOOGLE_TRANSLATE_PROJECT_ID
    || cfg.GCLOUD_TTS_PROJECTID
    || cfg.GOOGLE_TTS_PROJECT_ID
    || cfg.GOOGLE_SPEECH_PROJECT_ID
    || "";
  el.slideTranslateMaxFontSize.value = cfg.SLIDE_TRANSLATE_MAX_FONT_SIZE ?? 120;
  renderSlideTranslateStyleEditor(cfg.SLIDE_TRANSLATE_STYLES_JSON || "");
  el.gcloudTranslateProjectId.value = cfg.GCLOUD_TRANSLATE_PROJECTID || cfg.GOOGLE_TRANSLATE_PROJECT_ID || cfg.GCLOUD_TTS_PROJECTID || cfg.GOOGLE_TTS_PROJECT_ID || cfg.GOOGLE_SPEECH_PROJECT_ID || "";
  el.googleTranslateLocation.value = cfg.GOOGLE_TRANSLATE_LOCATION || "us-central1";
  el.geminiTextTranslateModel.value = cfg.TRANSCRIPT_TRANSLATE_MODEL || "gemini-2.5-pro";
  el.geminiTextTranslatePrompt.value = cfg.GEMINI_TEXT_TRANSLATE_PROMPT || "";
  el.googleTranslateSourceLanguageCode.value = cfg.GOOGLE_TRANSLATE_SOURCE_LANGUAGE_CODE || "";
  renderTermbaseEditor(cfg.TRANSLATION_TERMBASE_CSV || "");
  el.geminiTtsModel.value = cfg.GEMINI_TTS_MODEL || "gemini-2.5-flash-tts";
  el.geminiTtsVoice.value = cfg.GEMINI_TTS_VOICE || "Kore";
  el.gcloudTtsProjectId.value = cfg.GCLOUD_TTS_PROJECTID || cfg.GOOGLE_TTS_PROJECT_ID || cfg.GOOGLE_SPEECH_PROJECT_ID || "";
  el.geminiTtsPrompt.value = cfg.GEMINI_TTS_PROMPT || "";
  el.finalSlideUpscaleMode.value = cfg.FINAL_SLIDE_UPSCALE_MODE || "none";
  el.finalSlideUpscaleModel.value = cfg.FINAL_SLIDE_UPSCALE_MODEL || "caidas/swin2SR-classical-sr-x4-64";
  el.finalSlideUpscaleDevice.value = cfg.FINAL_SLIDE_UPSCALE_DEVICE || "auto";
  el.finalSlideUpscaleTileSize.value = cfg.FINAL_SLIDE_UPSCALE_TILE_SIZE ?? 256;
  el.finalSlideUpscaleTileOverlap.value = cfg.FINAL_SLIDE_UPSCALE_TILE_OVERLAP ?? 24;
  el.replicateNightmareRealesrganModelRef.value = cfg.REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF || "nightmareai/real-esrgan";
  el.replicateNightmareRealesrganVersionId.value = cfg.REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID || "f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa";
  el.replicateNightmareRealesrganPricePerSecond.value = cfg.REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND ?? 0.000225;
  el.replicateUpscaleConcurrency.value = cfg.REPLICATE_UPSCALE_CONCURRENCY ?? 2;
  el.videoExportMinSlideSec.value = cfg.VIDEO_EXPORT_MIN_SLIDE_SEC ?? 1.2;
  el.videoExportTailPadSec.value = cfg.VIDEO_EXPORT_TAIL_PAD_SEC ?? 0.35;
  el.videoExportIntroWhiteSec.value = cfg.VIDEO_EXPORT_INTRO_WHITE_SEC ?? 1.0;
  el.videoExportIntroFadeSec.value = cfg.VIDEO_EXPORT_INTRO_FADE_SEC ?? 0.4;
  el.videoExportThumbnailDurationSec.value = cfg.VIDEO_EXPORT_THUMBNAIL_DURATION_SEC ?? 2.0;
  el.videoExportThumbnailFadeSec.value = cfg.VIDEO_EXPORT_THUMBNAIL_FADE_SEC ?? 0.3;
  el.videoExportThumbnailTextLeadinSec.value = cfg.VIDEO_EXPORT_THUMBNAIL_TEXT_LEADIN_SEC ?? 1.0;
  el.videoExportIntroColor.value = cfg.VIDEO_EXPORT_INTRO_COLOR || "white";
  el.videoExportOutroHoldSec.value = cfg.VIDEO_EXPORT_OUTRO_HOLD_SEC ?? 1.5;
  el.videoExportOutroFadeSec.value = cfg.VIDEO_EXPORT_OUTRO_FADE_SEC ?? 1.5;
  el.videoExportOutroFadeColor.value = cfg.VIDEO_EXPORT_OUTRO_FADE_COLOR || "black";
  el.videoExportOutroBlackSec.value = cfg.VIDEO_EXPORT_OUTRO_BLACK_SEC ?? 2.0;
  el.videoExportWidth.value = cfg.VIDEO_EXPORT_WIDTH ?? 1920;
  el.videoExportHeight.value = cfg.VIDEO_EXPORT_HEIGHT ?? 1080;
  el.videoExportFps.value = cfg.VIDEO_EXPORT_FPS ?? 30;
  el.videoExportBgColor.value = cfg.VIDEO_EXPORT_BG_COLOR || "white";
  if (el.homeGeminiTextTranslateModel) {
    el.homeGeminiTextTranslateModel.value = cfg.TRANSCRIPT_TRANSLATE_MODEL || "gemini-2.5-pro";
  }
  if (el.homeGeminiTtsModel) {
    el.homeGeminiTtsModel.value = cfg.GEMINI_TTS_MODEL || "gemini-2.5-flash-tts";
  }
  if (el.homeFinalSlideUpscaleMode) {
    el.homeFinalSlideUpscaleMode.value = cfg.FINAL_SLIDE_UPSCALE_MODE || "none";
  }
  if (el.homeGeminiEditModel) {
    el.homeGeminiEditModel.value = cfg.GEMINI_EDIT_MODEL || "gemini-3-pro-image-preview";
  }
  if (el.homeGeminiTranslateModel) {
    el.homeGeminiTranslateModel.value = cfg.GEMINI_TRANSLATE_MODEL || "gemini-3-pro-image-preview";
  }
  clearHealthStatus("transcription");
  clearHealthStatus("slideEdit");
  clearHealthStatus("slideTranslate");
  clearHealthStatus("slideUpscale");
  clearHealthStatus("textTranslate");
  clearHealthStatus("tts");
  const videoLabel = cfg.VIDEO_PATH || "(nicht gesetzt)";
  el.configMeta.textContent = `VIDEO_PATH: ${videoLabel}`;
  syncSettingsFieldState();
  renderSelectedVideo(syncActionState);
}


export async function loadConfig(options = {}) {
  const cfg = await apiGet("/api/config");
  setConfig(cfg, options);
  return cfg;
}

export async function saveConfig(options = {}) {
  const videoPath = (state.selectedVideoPath || "").trim();
  const slideTranslateVisionProjectId = el.slideTranslateVisionProjectId.value.trim();
  const gcloudTranslateProjectId = el.gcloudTranslateProjectId.value.trim();
  const gcloudTtsProjectId = el.gcloudTtsProjectId.value.trim();
  const payload = {
    VIDEO_PATH: videoPath,
    ROI_X0: Number(el.roiX0.value),
    ROI_Y0: Number(el.roiY0.value),
    ROI_X1: Number(el.roiX1.value),
    ROI_Y1: Number(el.roiY1.value),
    RUN_STEP_EDIT: el.runStepEdit.checked ? 1 : 0,
    RUN_STEP_TRANSLATE: el.runStepTranslate.checked ? 1 : 0,
    RUN_STEP_UPSCALE: el.runStepUpscale.checked ? 1 : 0,
    RUN_STEP_TEXT_TRANSLATE: el.runStepTextTranslate.checked ? 1 : 0,
    RUN_STEP_TTS: el.runStepTts.checked ? 1 : 0,
    RUN_STEP_VIDEO_EXPORT: el.runStepVideoExport.checked ? 1 : 0,
    TRANSCRIPTION_PROVIDER: el.transcriptionProvider.value,
    WHISPER_MODEL: el.whisperModel.value.trim(),
    WHISPER_DEVICE: el.whisperDevice.value.trim(),
    WHISPER_COMPUTE_TYPE: el.whisperComputeType.value.trim(),
    WHISPER_LANGUAGE: el.whisperLanguage.value.trim(),
    GOOGLE_SPEECH_PROJECT_ID: el.googleSpeechProjectId.value.trim(),
    GOOGLE_SPEECH_LOCATION: el.googleSpeechLocation.value.trim(),
    GOOGLE_SPEECH_MODEL: el.googleSpeechModel.value.trim(),
    GOOGLE_SPEECH_LANGUAGE_CODES: el.googleSpeechLanguageCodes.value.trim(),
    GOOGLE_SPEECH_CHUNK_SEC: Number(el.googleSpeechChunkSec.value),
    GOOGLE_SPEECH_CHUNK_OVERLAP_SEC: Number(el.googleSpeechChunkOverlapSec.value),
    FINAL_SOURCE_MODE_AUTO: el.finalSourceModeAuto.value,
    FULLSLIDE_SAMPLE_FRAMES: Number(el.fullslideSampleFrames.value),
    FULLSLIDE_BORDER_STRIP_PX: Number(el.fullslideBorderStripPx.value),
    FULLSLIDE_MIN_MATCHED_SIDES: Number(el.fullslideMinMatchedSides.value),
    FULLSLIDE_BORDER_DIFF_THRESHOLD: Number(el.fullslideBorderDiffThreshold.value),
    FULLSLIDE_PERSON_BOX_AREA_RATIO: Number(el.fullslidePersonBoxAreaRatio.value),
    FULLSLIDE_PERSON_OUTSIDE_RATIO: Number(el.fullslidePersonOutsideRatio.value),
    KEYFRAME_SETTLE_FRAMES: Number(el.keyframeSettleFrames.value),
    KEYFRAME_STABLE_END_GUARD_FRAMES: Number(el.keyframeStableEndGuardFrames.value),
    KEYFRAME_STABLE_LOOKAHEAD_FRAMES: Number(el.keyframeStableLookaheadFrames.value),
    SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO: Number(el.speakerFilterMinStage1VideoRatio.value),
    SPEAKER_FILTER_MAX_EDGE_DENSITY: Number(el.speakerFilterMaxEdgeDensity.value),
    SPEAKER_FILTER_MAX_LAPLACIAN_VAR: Number(el.speakerFilterMaxLaplacianVar.value),
    SPEAKER_FILTER_MAX_DURATION_SEC: Number(el.speakerFilterMaxDurationSec.value),
    FINAL_SLIDE_POSTPROCESS_MODE: el.finalSlidePostprocessMode.value,
    GEMINI_EDIT_MODEL: el.geminiEditModel.value.trim(),
    GEMINI_EDIT_PROMPT: el.geminiEditPrompt.value,
    FINAL_SLIDE_TRANSLATION_MODE: el.finalSlideTranslationMode.value,
    FINAL_SLIDE_TARGET_LANGUAGE: (getSelectedTtsLanguageOption()?.label || "").trim(),
    GEMINI_TRANSLATE_MODEL: el.geminiTranslateModel.value.trim(),
    SLIDE_TRANSLATE_MAX_REVIEW_RETRIES: Number(el.geminiTranslateMaxReviewRetries.value),
    GEMINI_TRANSLATE_PROMPT: el.geminiTranslatePrompt.value,
    GCLOUD_VISION_PROJECTID: slideTranslateVisionProjectId,
    GOOGLE_VISION_PROJECT_ID: slideTranslateVisionProjectId,
    SLIDE_TRANSLATE_MAX_FONT_SIZE: Number(el.slideTranslateMaxFontSize.value),
    SLIDE_TRANSLATE_STYLES_JSON: (() => {
      syncSlideTranslateStylesJsonFromTable();
      return el.slideTranslateStylesJson.value;
    })(),
    GCLOUD_TRANSLATE_PROJECTID: gcloudTranslateProjectId,
    GOOGLE_TRANSLATE_PROJECT_ID: gcloudTranslateProjectId,
    GOOGLE_TRANSLATE_LOCATION: el.googleTranslateLocation.value.trim(),
    GOOGLE_TRANSLATE_MODEL: String(lastLoadedConfig.GOOGLE_TRANSLATE_MODEL || "general/translation-llm").trim(),
    TRANSCRIPT_TRANSLATE_MODEL: el.geminiTextTranslateModel.value.trim(),
    GEMINI_TEXT_TRANSLATE_PROMPT: el.geminiTextTranslatePrompt.value,
    GOOGLE_TRANSLATE_SOURCE_LANGUAGE_CODE: el.googleTranslateSourceLanguageCode.value.trim(),
    TRANSLATION_TERMBASE_CSV: (() => {
      syncTermbaseCsvFromTable();
      return el.translationTermbaseCsv.value;
    })(),
    GEMINI_TTS_MODEL: el.geminiTtsModel.value.trim(),
    GEMINI_TTS_VOICE: el.geminiTtsVoice.value.trim(),
    GCLOUD_TTS_PROJECTID: gcloudTtsProjectId,
    GOOGLE_TTS_PROJECT_ID: gcloudTtsProjectId,
    GOOGLE_TTS_LANGUAGE_CODE: (getSelectedTtsLanguageOption()?.tts_language_code || "").trim(),
    GEMINI_TTS_PROMPT: el.geminiTtsPrompt.value,
    FINAL_SLIDE_UPSCALE_MODE: el.finalSlideUpscaleMode.value,
    FINAL_SLIDE_UPSCALE_MODEL: el.finalSlideUpscaleModel.value.trim(),
    FINAL_SLIDE_UPSCALE_DEVICE: el.finalSlideUpscaleDevice.value,
    FINAL_SLIDE_UPSCALE_TILE_SIZE: Number(el.finalSlideUpscaleTileSize.value),
    FINAL_SLIDE_UPSCALE_TILE_OVERLAP: Number(el.finalSlideUpscaleTileOverlap.value),
    REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF: el.replicateNightmareRealesrganModelRef.value.trim(),
    REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID: el.replicateNightmareRealesrganVersionId.value.trim(),
    REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND: Number(el.replicateNightmareRealesrganPricePerSecond.value),
    REPLICATE_UPSCALE_CONCURRENCY: Number(el.replicateUpscaleConcurrency.value),
    VIDEO_EXPORT_MIN_SLIDE_SEC: Number(el.videoExportMinSlideSec.value),
    VIDEO_EXPORT_TAIL_PAD_SEC: Number(el.videoExportTailPadSec.value),
    VIDEO_EXPORT_INTRO_WHITE_SEC: Number(el.videoExportIntroWhiteSec.value),
    VIDEO_EXPORT_INTRO_FADE_SEC: Number(el.videoExportIntroFadeSec.value),
    VIDEO_EXPORT_THUMBNAIL_DURATION_SEC: Number(el.videoExportThumbnailDurationSec.value),
    VIDEO_EXPORT_THUMBNAIL_FADE_SEC: Number(el.videoExportThumbnailFadeSec.value),
    VIDEO_EXPORT_THUMBNAIL_TEXT_LEADIN_SEC: Number(el.videoExportThumbnailTextLeadinSec.value),
    VIDEO_EXPORT_INTRO_COLOR: el.videoExportIntroColor.value.trim(),
    VIDEO_EXPORT_OUTRO_HOLD_SEC: Number(el.videoExportOutroHoldSec.value),
    VIDEO_EXPORT_OUTRO_FADE_SEC: Number(el.videoExportOutroFadeSec.value),
    VIDEO_EXPORT_OUTRO_FADE_COLOR: el.videoExportOutroFadeColor.value.trim(),
    VIDEO_EXPORT_OUTRO_BLACK_SEC: Number(el.videoExportOutroBlackSec.value),
    VIDEO_EXPORT_WIDTH: Number(el.videoExportWidth.value),
    VIDEO_EXPORT_HEIGHT: Number(el.videoExportHeight.value),
    VIDEO_EXPORT_FPS: Number(el.videoExportFps.value),
    VIDEO_EXPORT_BG_COLOR: el.videoExportBgColor.value.trim(),
  };
  await apiPost("/api/config", payload);
  return await loadConfig(options);
}


export function syncSettingsFieldState() {
  const editEnabled = el.runStepEdit.checked;
  const translateEnabled = el.runStepTranslate.checked;
  const upscaleEnabled = el.runStepUpscale.checked;
  const textTranslateEnabled = el.runStepTextTranslate.checked;
  const ttsEnabled = el.runStepTts.checked;
  const videoExportEnabled = el.runStepVideoExport.checked;
  const transcriptionProvider = el.transcriptionProvider.value;
  const translationMode = el.finalSlideTranslationMode.value;
  const geminiSlideTranslate = translationMode === "gemini";
  const deterministicSlideTranslate = translationMode === "deterministic_glossary";
  const upscaleMode = el.finalSlideUpscaleMode.value;
  const localUpscale = upscaleMode === "swin2sr";
  const replicateUpscale = upscaleMode === "replicate_nightmare_realesrgan";
  const replicateNightmareUpscale = upscaleMode === "replicate_nightmare_realesrgan";
  const slideUpscaleApiEnabled = upscaleEnabled && upscaleMode !== "none";
  const googleTranscription = transcriptionProvider === "google_chirp_3";
  const textTranslateModel = String(el.geminiTextTranslateModel.value || "").trim().toLowerCase();
  const textTranslateUsesGeminiApi = textTranslateModel.startsWith("gemini-");
  const cloudTranslateConfigEnabled = (textTranslateEnabled && !textTranslateUsesGeminiApi)
    || (translateEnabled && deterministicSlideTranslate);
  const sourceLanguageConfigEnabled = textTranslateEnabled || (translateEnabled && deterministicSlideTranslate);

  el.whisperModel.disabled = googleTranscription;
  el.whisperDevice.disabled = googleTranscription;
  el.whisperComputeType.disabled = googleTranscription;
  el.whisperLanguage.disabled = googleTranscription;
  el.googleSpeechProjectId.disabled = !googleTranscription;
  el.googleSpeechLocation.disabled = !googleTranscription;
  el.googleSpeechModel.disabled = !googleTranscription;
  el.googleSpeechLanguageCodes.disabled = !googleTranscription;
  el.googleSpeechChunkSec.disabled = !googleTranscription;
  el.googleSpeechChunkOverlapSec.disabled = !googleTranscription;
  if (el.transcriptionHealthCheck) {
    el.transcriptionHealthCheck.disabled = !googleTranscription;
  }
  if (!googleTranscription) {
    setHealthStatus("transcription", "idle", "Only for google_chirp_3.", "");
  } else if (el.transcriptionHealthStatus?.textContent === "Only for google_chirp_3.") {
    clearHealthStatus("transcription");
  }

  el.finalSlidePostprocessMode.disabled = !editEnabled;
  el.geminiEditModel.disabled = !editEnabled;
  el.geminiEditPrompt.disabled = !editEnabled;
  const editApiEnabled = editEnabled && el.finalSlidePostprocessMode.value === "gemini";
  if (el.slideEditHealthCheck) {
    el.slideEditHealthCheck.disabled = !editApiEnabled;
  }
  if (!editApiEnabled) {
    setHealthStatus("slideEdit", "idle", editEnabled ? "Only for nano banana mode." : "Step disabled.", "");
  } else if (
    el.slideEditHealthStatus?.textContent === "Only for nano banana mode."
    || el.slideEditHealthStatus?.textContent === "Step disabled."
  ) {
    clearHealthStatus("slideEdit");
  }

  el.finalSlideTranslationMode.disabled = !translateEnabled;
  const languageSelectionEnabled = translateEnabled || textTranslateEnabled || ttsEnabled || googleTranscription;
  if (el.finalSlideTargetLanguageSearch) {
    el.finalSlideTargetLanguageSearch.disabled = !languageSelectionEnabled;
  }
  el.finalSlideTargetLanguage.disabled = !languageSelectionEnabled;
  el.geminiTranslateModel.disabled = !translateEnabled || !geminiSlideTranslate;
  el.geminiTranslateMaxReviewRetries.disabled = !translateEnabled || !geminiSlideTranslate;
  el.geminiTranslatePrompt.disabled = !translateEnabled || !geminiSlideTranslate;
  el.slideTranslateVisionProjectId.disabled = !translateEnabled || !deterministicSlideTranslate;
  el.slideTranslateMaxFontSize.disabled = !translateEnabled || !deterministicSlideTranslate;
  setSlideTranslateStyleEditorDisabled(!translateEnabled || !deterministicSlideTranslate);
  const slideTranslateApiEnabled = translateEnabled && el.finalSlideTranslationMode.value !== "none";
  if (el.slideTranslateHealthCheck) {
    el.slideTranslateHealthCheck.disabled = !slideTranslateApiEnabled;
  }
  if (!slideTranslateApiEnabled) {
    setHealthStatus("slideTranslate", "idle", translateEnabled ? "Mode none." : "Step disabled.", "");
  } else if (
    el.slideTranslateHealthStatus?.textContent === "Mode none."
    || el.slideTranslateHealthStatus?.textContent === "Step disabled."
  ) {
    clearHealthStatus("slideTranslate");
  }

  el.gcloudTranslateProjectId.disabled = !cloudTranslateConfigEnabled;
  el.googleTranslateLocation.disabled = !cloudTranslateConfigEnabled;
  el.geminiTextTranslateModel.disabled = !textTranslateEnabled;
  el.geminiTextTranslatePrompt.disabled = !textTranslateEnabled;
  el.googleTranslateSourceLanguageCode.disabled = !sourceLanguageConfigEnabled;
  if (el.textTranslateHealthCheck) {
    el.textTranslateHealthCheck.disabled = !textTranslateEnabled;
  }
  if (!textTranslateEnabled) {
    setHealthStatus("textTranslate", "idle", "Step disabled.", "");
  } else if (el.textTranslateHealthStatus?.textContent === "Step disabled.") {
    clearHealthStatus("textTranslate");
  }

  el.geminiTtsModel.disabled = !ttsEnabled;
  el.geminiTtsVoice.disabled = !ttsEnabled;
  el.gcloudTtsProjectId.disabled = !ttsEnabled;
  el.googleTtsLanguageCode.disabled = !ttsEnabled;
  el.geminiTtsPrompt.disabled = !ttsEnabled;
  if (el.ttsHealthCheck) {
    el.ttsHealthCheck.disabled = !ttsEnabled;
  }
  if (!ttsEnabled) {
    setHealthStatus("tts", "idle", "Step disabled.", "");
  } else if (el.ttsHealthStatus?.textContent === "Step disabled.") {
    clearHealthStatus("tts");
  }

  updateTtsLanguageHint();

  el.finalSlideUpscaleMode.disabled = !upscaleEnabled;
  el.finalSlideUpscaleModel.disabled = !upscaleEnabled || !localUpscale;
  el.finalSlideUpscaleDevice.disabled = !upscaleEnabled || !localUpscale;
  el.finalSlideUpscaleTileSize.disabled = !upscaleEnabled || !localUpscale;
  el.finalSlideUpscaleTileOverlap.disabled = !upscaleEnabled || !localUpscale;
  el.replicateNightmareRealesrganModelRef.disabled = !upscaleEnabled || !replicateNightmareUpscale;
  el.replicateNightmareRealesrganVersionId.disabled = !upscaleEnabled || !replicateNightmareUpscale;
  el.replicateNightmareRealesrganPricePerSecond.disabled = !upscaleEnabled || !replicateNightmareUpscale;
  el.replicateUpscaleConcurrency.disabled = !upscaleEnabled || !replicateUpscale;
  if (el.slideUpscaleHealthCheck) {
    el.slideUpscaleHealthCheck.disabled = !slideUpscaleApiEnabled;
  }
  if (!slideUpscaleApiEnabled) {
    setHealthStatus("slideUpscale", "idle", upscaleEnabled ? "Select an upscale mode." : "Step disabled.", "");
  } else if (
    el.slideUpscaleHealthStatus?.textContent === "Select an upscale mode."
    || el.slideUpscaleHealthStatus?.textContent === "Step disabled."
  ) {
    clearHealthStatus("slideUpscale");
  }

  el.videoExportMinSlideSec.disabled = !videoExportEnabled;
  el.videoExportTailPadSec.disabled = !videoExportEnabled;
  el.videoExportWidth.disabled = !videoExportEnabled;
  el.videoExportHeight.disabled = !videoExportEnabled;
  el.videoExportFps.disabled = !videoExportEnabled;
  el.videoExportBgColor.disabled = !videoExportEnabled;
  syncStepSections();
}
