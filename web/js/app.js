import { el } from "./dom.js";
import { state } from "./state.js";
import { formatRunIdLabel, getInitialActiveTab, setActiveTab, showButtonSuccess, syncSettingsKeyTooltips } from "./ui-core.js";
import { syncRunFavicon } from "./favicon.js";
import {
  clearHealthStatus,
  testGeminiHealth,
  testSpeechToTextHealth,
  testCloudTranslationHealth,
  testCloudVisionHealth,
  testCloudTtsHealth,
  testReplicateHealth,
  toggleHealthMeta,
} from "./health-checks.js";
import {
  getSelectedTtsLanguageOption,
  renderTtsLanguageOptions,
  syncSelectedTtsLanguage,
  updateTtsLanguageHint,
} from "./tts-language.js";
import {
  addTermbaseRow,
  loadConfig,
  renderSlideTranslateStyleEditor,
  saveConfig,
  syncSettingsFieldState,
  syncStepSections,
  toggleSlideTranslateStyleEditor,
  toggleTermbaseEditor,
} from "./settings.js";
import {
  closeImageModal,
  closeRoiStatusModal,
  closeStatusModal,
  closeVideoPicker,
  handleImageModalWheel,
  openRoiStatusModal,
  openStatusModal,
  openVideoPicker,
} from "./modals.js";
import {
  configureRunsModule,
  loadLatestRunDetails,
  loadLatestSlides,
  loadOverlay,
  loadRunDetails,
  loadRunSlides,
  loadRuns,
  pollCurrent,
  regenerateOverlay,
  retryRun,
  startRun,
  stopRun,
} from "./runs.js";

function setStatus(current) {
  const status = current.status || "idle";
  state.currentRunStatus = status;
  syncRunFavicon(status);
  state.currentRunId = current.run_id || null;
  const runId = current.run_id ? `, run ${formatRunIdLabel(current.run_id)}` : "";
  if (el.statusSummary) {
    el.statusSummary.textContent = `status: ${status}${runId}`;
  }
  renderRunSteps(current);
  syncActionState();

  const logs = (current.log_tail || []).slice(-120);
  const nextLog = logs.join("\n");
  if (el.runLog.textContent !== nextLog) {
    el.runLog.textContent = nextLog;
    el.runLog.scrollTop = el.runLog.scrollHeight;
  }
}

function syncActionState() {
  const hasVideo = Boolean((state.selectedVideoPath || "").trim());
  const isBusyRun = state.currentRunStatus === "running" || state.currentRunStatus === "stopping";
  el.startRun.disabled = isBusyRun || !hasVideo;
  el.regenOverlay.disabled = !hasVideo;
  if (el.stopRun) {
    el.stopRun.disabled = state.currentRunStatus !== "running";
    el.stopRun.textContent = state.currentRunStatus === "stopping" ? "Stopping..." : "Stop Run";
  }
  if (el.retryRun) {
    el.retryRun.disabled = state.currentRunStatus !== "error" && state.currentRunStatus !== "stopped";
  }
}

function renderRunSteps(current) {
  const steps = Array.isArray(current?.steps) ? current.steps : [];
  el.runSteps.innerHTML = "";
  if (steps.length === 0) return;

  for (const step of steps) {
    const row = document.createElement("div");
    row.className = `step-item is-${step.status || "pending"}`;

    const icon = document.createElement("span");
    icon.className = `step-icon is-${step.status || "pending"}`;
    icon.setAttribute("aria-hidden", "true");
    row.appendChild(icon);

    const body = document.createElement("div");
    body.className = "step-body";

    const head = document.createElement("div");
    head.className = "step-head";

    const label = document.createElement("span");
    label.className = "step-label";
    label.textContent = step.label || step.id || "Step";
    head.appendChild(label);

    const stateText = document.createElement("span");
    stateText.className = "step-state";
    stateText.textContent = step.status || "pending";
    head.appendChild(stateText);
    body.appendChild(head);

    const detail = document.createElement("div");
    detail.className = "step-detail";
    detail.textContent = step.detail || " ";
    body.appendChild(detail);

    row.appendChild(body);
    el.runSteps.appendChild(row);
  }
}

function bindEvents() {
  if (el.topbarHome) {
    el.topbarHome.addEventListener("click", () => setActiveTab("home"));
  }

  for (const btn of el.tabButtons) {
    btn.addEventListener("click", () => setActiveTab(btn.dataset.tab));
  }

  async function applyHomeQuickSettings() {
    if (el.homeTranscriptionProvider && el.transcriptionProvider) {
      el.transcriptionProvider.value = el.homeTranscriptionProvider.value;
    }
    if (el.homeTargetLanguage && el.finalSlideTargetLanguage) {
      const wantedCode = String(el.homeTargetLanguage.value || "").trim();
      if (el.finalSlideTargetLanguageSearch) {
        el.finalSlideTargetLanguageSearch.value = "";
      }
      const wanted = (Array.isArray(state.ttsLanguageOptions) ? state.ttsLanguageOptions : [])
        .find((item) => item.tts_language_code === wantedCode);
      renderTtsLanguageOptions("", wantedCode, wanted?.label || "");
      syncSelectedTtsLanguage();
    }
    if (el.homeGeminiTextTranslateModel && el.geminiTextTranslateModel) {
      el.geminiTextTranslateModel.value = el.homeGeminiTextTranslateModel.value;
    }
    if (el.homeGeminiTtsModel && el.geminiTtsModel) {
      el.geminiTtsModel.value = el.homeGeminiTtsModel.value;
    }
    if (el.homeFinalSlideUpscaleMode && el.finalSlideUpscaleMode) {
      el.finalSlideUpscaleMode.value = el.homeFinalSlideUpscaleMode.value;
    }
    if (el.homeGeminiEditModel && el.geminiEditModel) {
      el.geminiEditModel.value = el.homeGeminiEditModel.value;
    }
    if (el.homeGeminiTranslateModel && el.geminiTranslateModel) {
      el.geminiTranslateModel.value = el.homeGeminiTranslateModel.value;
    }
    syncSettingsFieldState();
    await saveConfig({ syncActionState });
  }

  [
    el.homeTranscriptionProvider,
    el.homeTargetLanguage,
    el.homeGeminiTextTranslateModel,
    el.homeGeminiTtsModel,
    el.homeFinalSlideUpscaleMode,
    el.homeGeminiEditModel,
    el.homeGeminiTranslateModel,
  ].forEach((input) => {
    if (!input) return;
    input.addEventListener("change", () => runTask(applyHomeQuickSettings));
  });

  el.saveRoi.addEventListener("click", () => runTask(async () => {
    await saveConfig({ syncActionState });
    showButtonSuccess(el.saveRoi, "Saved");
  }));

  el.saveSettings.addEventListener("click", () => runTask(async () => {
    await saveConfig({ syncActionState });
    showButtonSuccess(el.saveSettings, "Saved", "Settings saved.");
  }));
  if (el.termbaseEditorToggle) {
    el.termbaseEditorToggle.addEventListener("click", toggleTermbaseEditor);
  }
  if (el.termbaseAddRow) {
    el.termbaseAddRow.addEventListener("click", addTermbaseRow);
  }
  if (el.slideTranslateStyleEditorToggle) {
    el.slideTranslateStyleEditorToggle.addEventListener("click", toggleSlideTranslateStyleEditor);
  }

  if (el.geminiHealthCheck) {
    el.geminiHealthCheck.addEventListener("click", () => runTask(testGeminiHealth));
  }
  if (el.speechToTextHealthCheck) {
    el.speechToTextHealthCheck.addEventListener("click", () => runTask(testSpeechToTextHealth));
  }
  if (el.cloudTranslationHealthCheck) {
    el.cloudTranslationHealthCheck.addEventListener("click", () => runTask(testCloudTranslationHealth));
  }
  if (el.cloudVisionHealthCheck) {
    el.cloudVisionHealthCheck.addEventListener("click", () => runTask(testCloudVisionHealth));
  }
  if (el.cloudTtsHealthCheck) {
    el.cloudTtsHealthCheck.addEventListener("click", () => runTask(testCloudTtsHealth));
  }
  if (el.replicateHealthCheck) {
    el.replicateHealthCheck.addEventListener("click", () => runTask(testReplicateHealth));
  }
  [
    ["gemini", el.geminiHealthMetaToggle],
    ["speechToText", el.speechToTextHealthMetaToggle],
    ["cloudTranslation", el.cloudTranslationHealthMetaToggle],
    ["cloudVision", el.cloudVisionHealthMetaToggle],
    ["cloudTts", el.cloudTtsHealthMetaToggle],
    ["replicate", el.replicateHealthMetaToggle],
  ].forEach(([key, button]) => {
    if (button) {
      button.addEventListener("click", () => toggleHealthMeta(key));
    }
  });

  el.regenOverlay.addEventListener("click", () => runTask(async () => {
    await regenerateOverlay();
    showButtonSuccess(el.regenOverlay, "Generated");
  }));

  el.refreshOverlay.addEventListener("click", () => runTask(async () => {
    await loadOverlay();
    showButtonSuccess(el.refreshOverlay, "Refreshed");
  }));

  el.openRoiStatus.addEventListener("click", openRoiStatusModal);

  el.startRun.addEventListener("click", () => runTask(async () => {
    await startRun();
    showButtonSuccess(el.startRun, "Started");
  }));

  el.openStatus.addEventListener("click", openStatusModal);
  el.stopRun.addEventListener("click", () => runTask(stopRun));
  if (el.retryRun) {
    el.retryRun.addEventListener("click", () => runTask(async () => {
      await retryRun();
      showButtonSuccess(el.retryRun, "Retrying");
    }));
  }

  el.refreshRuns.addEventListener("click", () => runTaskImmediate(async () => {
    await loadRuns();
    showButtonSuccess(el.refreshRuns, "Refreshed");
  }));

  el.pickVideo.addEventListener("click", () => runTask(() => openVideoPicker({
    runTask,
    saveConfig: () => saveConfig({ syncActionState }),
    successButton: el.pickVideo,
  })));

  el.pickVideoRoi.addEventListener("click", () => runTask(() => openVideoPicker({
    runTask,
    saveConfig: () => saveConfig({ syncActionState }),
    successButton: el.pickVideoRoi,
  })));

  el.transcriptionProvider.addEventListener("change", syncSettingsFieldState);
  el.finalSlideUpscaleMode.addEventListener("change", syncSettingsFieldState);
  el.finalSlideTranslationMode.addEventListener("change", syncSettingsFieldState);

  for (const input of [
    el.runStepEdit,
    el.runStepTranslate,
    el.runStepUpscale,
    el.runStepTextTranslate,
    el.runStepTts,
    el.runStepVideoExport,
  ]) {
    input.addEventListener("change", syncSettingsFieldState);
  }

  // GCLOUD_PROJECT_ID change clears all 6 health statuses
  if (el.gcloudProjectId) {
    const clearAll = () => {
      clearHealthStatus("gemini");
      clearHealthStatus("speechToText");
      clearHealthStatus("cloudTranslation");
      clearHealthStatus("cloudVision");
      clearHealthStatus("cloudTts");
      clearHealthStatus("replicate");
    };
    el.gcloudProjectId.addEventListener("input", clearAll);
    el.gcloudProjectId.addEventListener("change", clearAll);
  }

  for (const input of [el.geminiEditModel]) {
    input.addEventListener("input", () => clearHealthStatus("gemini"));
    input.addEventListener("change", () => clearHealthStatus("gemini"));
  }

  for (const input of [
    el.transcriptionProvider,
    el.googleSpeechLocation,
    el.googleSpeechModel,
    el.googleSpeechLanguageCodes,
  ]) {
    input.addEventListener("input", () => clearHealthStatus("speechToText"));
    input.addEventListener("change", () => clearHealthStatus("speechToText"));
  }

  for (const input of [
    el.googleTranslateLocation,
    el.googleTranslateSourceLanguageCode,
    el.finalSlideTargetLanguageSearch,
    el.finalSlideTargetLanguage,
  ]) {
    input.addEventListener("input", () => clearHealthStatus("cloudTranslation"));
    input.addEventListener("change", () => clearHealthStatus("cloudTranslation"));
  }
  if (el.termbaseTableBody) {
    el.termbaseTableBody.addEventListener("input", () => clearHealthStatus("cloudTranslation"));
    el.termbaseTableBody.addEventListener("change", () => clearHealthStatus("cloudTranslation"));
  }

  for (const input of [
    el.finalSlideTargetLanguageSearch,
    el.finalSlideTargetLanguage,
    el.geminiTtsModel,
    el.geminiTtsVoice,
    el.geminiTtsPrompt,
  ]) {
    input.addEventListener("input", () => clearHealthStatus("cloudTts"));
    input.addEventListener("change", () => clearHealthStatus("cloudTts"));
  }

  for (const input of [
    el.replicateNightmareRealesrganModelRef,
    el.replicateNightmareRealesrganVersionId,
    el.replicateNightmareRealesrganPricePerSecond,
  ]) {
    input.addEventListener("input", () => clearHealthStatus("replicate"));
    input.addEventListener("change", () => clearHealthStatus("replicate"));
  }

  for (const input of [
    el.finalSlideTargetLanguageSearch,
    el.finalSlideTargetLanguage,
    el.runStepTts,
    el.runStepTextTranslate,
  ]) {
    input.addEventListener("input", updateTtsLanguageHint);
    input.addEventListener("change", updateTtsLanguageHint);
  }

  if (el.finalSlideTargetLanguageSearch) {
    el.finalSlideTargetLanguageSearch.addEventListener("input", () => {
      const selected = getSelectedTtsLanguageOption();
      renderTtsLanguageOptions(
        el.finalSlideTargetLanguageSearch.value,
        selected?.tts_language_code || "",
        selected?.label || "",
      );
    });
  }
  el.finalSlideTargetLanguage.addEventListener("change", syncSelectedTtsLanguage);

  document.querySelectorAll(".step-section-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const sectionId = button.dataset.stepToggle;
      if (!sectionId || button.disabled) return;
      state.stepSectionExpanded[sectionId] = !state.stepSectionExpanded[sectionId];
      syncStepSections();
    });
  });

  el.latestViewMode.addEventListener("change", () => {
    state.latestSlidesMode = el.latestViewMode.value === "base" ? "base" : "final";
    runTaskImmediate(loadLatestSlides);
  });
  el.latestFinalSourceMode.addEventListener("change", () => {
    state.latestFinalSourceMode = ["raw", "translated"].includes(el.latestFinalSourceMode.value)
      ? el.latestFinalSourceMode.value
      : "processed";
    runTaskImmediate(loadLatestSlides);
  });
  el.latestFinalDisplayMode.addEventListener("change", () => {
    state.latestFinalDisplayMode = el.latestFinalDisplayMode.value === "compare" ? "compare" : "single";
    runTaskImmediate(loadLatestSlides);
  });
  if (el.latestShowOriginalText) {
    el.latestShowOriginalText.addEventListener("change", () => {
      state.latestShowOriginalText = el.latestShowOriginalText.checked;
      runTaskImmediate(loadLatestSlides);
    });
  }

  el.latestInfoToggle.addEventListener("click", () => {
    state.latestInfoExpanded = !state.latestInfoExpanded;
    el.latestInfoWrap.classList.toggle("is-open", state.latestInfoExpanded);
    el.latestInfoPanel.hidden = !state.latestInfoExpanded;
    el.latestInfoToggle.setAttribute("aria-expanded", state.latestInfoExpanded ? "true" : "false");
  });

  el.runViewMode.addEventListener("change", () => {
    state.runSlidesMode = el.runViewMode.value === "base" ? "base" : "final";
    runTaskImmediate(loadRunSlides);
  });
  el.runFinalSourceMode.addEventListener("change", () => {
    state.runFinalSourceMode = ["raw", "translated"].includes(el.runFinalSourceMode.value)
      ? el.runFinalSourceMode.value
      : "processed";
    runTaskImmediate(loadRunSlides);
  });
  el.runFinalDisplayMode.addEventListener("change", () => {
    state.runFinalDisplayMode = el.runFinalDisplayMode.value === "compare" ? "compare" : "single";
    runTaskImmediate(loadRunSlides);
  });
  if (el.runShowOriginalText) {
    el.runShowOriginalText.addEventListener("change", () => {
      state.runShowOriginalText = el.runShowOriginalText.checked;
      runTaskImmediate(loadRunSlides);
    });
  }

  el.imageModalClose.addEventListener("click", closeImageModal);
  el.imageModalBackdrop.addEventListener("click", closeImageModal);
  if (el.imageModalViewport) {
    el.imageModalViewport.addEventListener("wheel", handleImageModalWheel, { passive: false });
  }
  el.statusModalClose.addEventListener("click", closeStatusModal);
  el.statusModalBackdrop.addEventListener("click", closeStatusModal);
  el.roiStatusModalClose.addEventListener("click", closeRoiStatusModal);
  el.roiStatusModalBackdrop.addEventListener("click", closeRoiStatusModal);
  el.videoPickerClose.addEventListener("click", closeVideoPicker);
  el.videoPickerBackdrop.addEventListener("click", closeVideoPicker);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && el.imageModal.classList.contains("open")) {
      closeImageModal();
    }
    if (e.key === "Escape" && el.statusModal.classList.contains("open")) {
      closeStatusModal();
    }
    if (e.key === "Escape" && el.roiStatusModal.classList.contains("open")) {
      closeRoiStatusModal();
    }
    if (e.key === "Escape" && el.videoPickerModal.classList.contains("open")) {
      closeVideoPicker();
    }
  });
}

let busy = false;
async function runTask(fn) {
  if (busy) return;
  busy = true;
  try {
    await fn();
  } catch (err) {
    alert(err.message || String(err));
  } finally {
    busy = false;
  }
}

async function runTaskImmediate(fn) {
  try {
    await fn();
  } catch (err) {
    alert(err.message || String(err));
  }
}

async function init() {
  configureRunsModule({ runTaskImmediate, setStatus });
  bindEvents();
  syncSettingsKeyTooltips();

  state.latestSlidesMode = el.latestViewMode.value === "base" ? "base" : "final";
  state.latestFinalSourceMode = ["raw", "translated"].includes(el.latestFinalSourceMode.value)
    ? el.latestFinalSourceMode.value
    : "processed";
  state.latestFinalDisplayMode = el.latestFinalDisplayMode.value === "compare" ? "compare" : "single";
  state.latestShowOriginalText = Boolean(el.latestShowOriginalText?.checked ?? true);
  state.runSlidesMode = el.runViewMode.value === "base" ? "base" : "final";
  state.runFinalSourceMode = ["raw", "translated"].includes(el.runFinalSourceMode.value)
    ? el.runFinalSourceMode.value
    : "processed";
  state.runFinalDisplayMode = el.runFinalDisplayMode.value === "compare" ? "compare" : "single";
  state.runShowOriginalText = Boolean(el.runShowOriginalText?.checked ?? true);
  syncSettingsFieldState();
  setActiveTab(getInitialActiveTab());

  await runTask(() => loadConfig({ syncActionState }));
  await runTask(loadOverlay);
  await runTask(loadRuns);
  window.setInterval(pollCurrent, 2000);
}

init();
