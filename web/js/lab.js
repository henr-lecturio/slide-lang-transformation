import { el } from "./dom.js";
import { state } from "./state.js";
import { apiGet, apiPost } from "./api.js";
import { formatUsd } from "./ui-core.js";
import { openImageModal } from "./modals.js";

const LAB_TEST_SETTINGS_STORAGE_KEY = "slide-transform-lab-test-settings";
const ALLOWED_IMAGE_MODELS = new Set([
  "gemini-3.1-flash-image-preview",
  "gemini-3-pro-image-preview",
  "gemini-2.5-flash-image",
]);

function setNodeText(node, text) {
  if (node) node.textContent = text;
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
  const geminiTranslateMode = translateMode !== "deterministic_glossary";
  if (el.labGeminiTranslateModel) {
    el.labGeminiTranslateModel.disabled = !geminiTranslateMode;
  }
  if (el.labGeminiTranslatePrompt) {
    el.labGeminiTranslatePrompt.disabled = !geminiTranslateMode;
  }
}

function applyLabTestSettingsToForm() {
  ensureLabTestSettings();
  el.labGeminiEditModel.value = state.labTestSettings.slide_edit_model;
  el.labGeminiEditPrompt.value = state.labTestSettings.slide_edit_prompt;
  renderLabTargetLanguageOptions();
  el.labGeminiTranslateModel.value = state.labTestSettings.slide_translate_model;
  el.labGeminiTranslatePrompt.value = state.labTestSettings.slide_translate_prompt;
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
  state.labTestSettings = normalizeLabTestSettings({
    slide_edit_model: el.labGeminiEditModel.value,
    slide_edit_prompt: el.labGeminiEditPrompt.value,
    target_language: el.labFinalSlideTargetLanguage.value,
    slide_translate_model: el.labGeminiTranslateModel.value,
    slide_translate_prompt: el.labGeminiTranslatePrompt.value,
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
    setNodeText(el.labSelectedImage, "Kein Bild gewählt.");
    el.labOriginalImage.removeAttribute("src");
    el.labOriginalImage.onclick = null;
    syncLabActionState();
    return;
  }
  const metaText = `run=${item.run_id} | event=${item.event_id} | ${Number(item.slide_start || 0).toFixed(2)}s - ${Number(item.slide_end || 0).toFixed(2)}s | ${item.name}`;
  setNodeText(el.labSelectedImage, metaText);
  el.labOriginalImage.src = `${item.image_url}?v=${Date.now()}`;
  el.labOriginalImage.onclick = () => openImageModal(item.image_url, item.name || `event_${item.event_id}`);
  syncLabActionState();
}

export function setLabStatus(current) {
  const status = current?.status || "idle";
  state.labStatus = status;
  const action = current?.action ? ` | action=${current.action}` : "";
  const provider = current?.provider ? ` | provider=${current.provider}` : "";
  const jobId = current?.job_id ? ` | job=${current.job_id}` : "";
  setNodeText(el.labJobStatus, `status: ${status}${action}${provider}${jobId}`);
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
    setNodeText(
      el.labSelectedImage,
      current.input_name
        ? `Letzter Testinput: ${current.input_name}`
        : "Letzter Testinput",
    );
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
