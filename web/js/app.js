import { el } from "./dom.js";
import { state } from "./state.js";
import { formatRunIdLabel, getInitialActiveTab, setActiveTab, showButtonSuccess, syncSettingsKeyTooltips } from "./ui-core.js";
import {
  clearHealthStatus,
  testSlideEditHealth,
  testSlideTranslateHealth,
  testSlideUpscaleHealth,
  testTextTranslateHealth,
  testTranscriptionHealth,
  testTtsHealth,
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
  saveConfig,
  syncSettingsFieldState,
  syncStepSections,
  toggleTermbaseEditor,
} from "./settings.js";
import {
  closeImageModal,
  closeExportLabRunPicker,
  closeExportLabSettingsModal,
  closeExportLabStatusModal,
  closeLabImagePicker,
  closeLabStatusModal,
  closeLabSettingsModal,
  closeRoiStatusModal,
  closeStatusModal,
  closeVideoPicker,
  openExportLabRunPicker,
  openExportLabSettingsModal,
  openExportLabStatusModal,
  openLabImagePicker,
  openLabStatusModal,
  openLabSettingsModal,
  openRoiStatusModal,
  openStatusModal,
  openVideoPicker,
} from "./modals.js";
import {
  initializeExportLabTestSettings,
  loadExportLabStatus,
  renderExportLabSelection,
  resetExportLabTestSettingsFromCurrentSettings,
  runExportLabAction,
  saveExportLabTestSettings,
  stopExportLabJob,
  syncExportLabActionState,
  syncExportLabTestSections,
} from "./export-lab.js";
import {
  initializeLabTestSettings,
  loadLabStatus,
  renderLabSelection,
  resetLabTestSettingsFromCurrentSettings,
  runLabAction,
  saveLabTestSettings,
  stopLabJob,
  syncLabTestSections,
  syncLabActionState,
} from "./lab.js";
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
  startRun,
  stopRun,
} from "./runs.js";

function setStatus(current) {
  const status = current.status || "idle";
  state.currentRunStatus = status;
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
  syncLabActionState();
  syncExportLabActionState();
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
      el.finalSlideTargetLanguage.value = el.homeTargetLanguage.value;
      syncSelectedTtsLanguage();
    }
    if (el.homeGeminiTextTranslateModel && el.geminiTextTranslateModel) {
      el.geminiTextTranslateModel.value = el.homeGeminiTextTranslateModel.value;
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

  el.ttsHealthCheck.addEventListener("click", () => runTask(testTtsHealth));
  if (el.transcriptionHealthCheck) {
    el.transcriptionHealthCheck.addEventListener("click", () => runTask(testTranscriptionHealth));
  }
  if (el.slideEditHealthCheck) {
    el.slideEditHealthCheck.addEventListener("click", () => runTask(testSlideEditHealth));
  }
  if (el.slideTranslateHealthCheck) {
    el.slideTranslateHealthCheck.addEventListener("click", () => runTask(testSlideTranslateHealth));
  }
  if (el.slideUpscaleHealthCheck) {
    el.slideUpscaleHealthCheck.addEventListener("click", () => runTask(testSlideUpscaleHealth));
  }
  if (el.textTranslateHealthCheck) {
    el.textTranslateHealthCheck.addEventListener("click", () => runTask(testTextTranslateHealth));
  }
  [
    ["transcription", el.transcriptionHealthMetaToggle],
    ["slideEdit", el.slideEditHealthMetaToggle],
    ["slideTranslate", el.slideTranslateHealthMetaToggle],
    ["slideUpscale", el.slideUpscaleHealthMetaToggle],
    ["textTranslate", el.textTranslateHealthMetaToggle],
    ["tts", el.ttsHealthMetaToggle],
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

  el.labPickImage.addEventListener("click", () => runTask(() => openLabImagePicker({ runTask, renderLabSelection })));
  el.labOpenSettings.addEventListener("click", () => runTask(async () => {
    initializeLabTestSettings();
    openLabSettingsModal();
  }));
  el.labOpenTerminal.addEventListener("click", openLabStatusModal);
  el.labStopRun.addEventListener("click", () => runTask(stopLabJob));
  el.labRunEdit.addEventListener("click", () => runTask(async () => {
    await runLabAction("edit");
    showButtonSuccess(el.labRunEdit, "Started");
  }));
  el.labRunTranslate.addEventListener("click", () => runTask(async () => {
    await runLabAction("translate");
    showButtonSuccess(el.labRunTranslate, "Started");
  }));
  el.labRunUpscale.addEventListener("click", () => runTask(async () => {
    await runLabAction("upscale");
    showButtonSuccess(el.labRunUpscale, "Started");
  }));
  el.labSettingsSave.addEventListener("click", () => runTask(async () => {
    saveLabTestSettings();
    showButtonSuccess(el.labSettingsSave, "Saved");
  }));
  el.labSettingsReset.addEventListener("click", () => runTask(async () => {
    resetLabTestSettingsFromCurrentSettings();
    showButtonSuccess(el.labSettingsReset, "Reset");
  }));
  el.labFinalSlideUpscaleMode.addEventListener("change", saveLabTestSettings);

  el.exportLabPickRun.addEventListener("click", () => runTask(() => openExportLabRunPicker({
    runTask,
    renderExportLabSelection,
  })));
  el.exportLabOpenSettings.addEventListener("click", () => runTask(async () => {
    initializeExportLabTestSettings();
    openExportLabSettingsModal();
  }));
  el.exportLabOpenTerminal.addEventListener("click", () => {
    openExportLabStatusModal();
    runTaskImmediate(loadExportLabStatus);
  });
  el.exportLabStopRun.addEventListener("click", () => runTask(stopExportLabJob));
  el.exportLabRunExport.addEventListener("click", () => runTask(async () => {
    await runExportLabAction();
    showButtonSuccess(el.exportLabRunExport, "Started");
  }));
  el.exportLabSettingsSave.addEventListener("click", () => runTask(async () => {
    saveExportLabTestSettings();
    showButtonSuccess(el.exportLabSettingsSave, "Saved");
  }));
  el.exportLabSettingsReset.addEventListener("click", () => runTask(async () => {
    resetExportLabTestSettingsFromCurrentSettings();
    showButtonSuccess(el.exportLabSettingsReset, "Reset");
  }));

  document.querySelectorAll(".export-lab-step-section-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const sectionId = button.dataset.exportLabStepToggle;
      if (!sectionId) return;
      state.exportLabStepSectionExpanded[sectionId] = !state.exportLabStepSectionExpanded[sectionId];
      syncExportLabTestSections();
    });
  });

  document.querySelectorAll(".lab-step-section-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const sectionId = button.dataset.labStepToggle;
      if (!sectionId) return;
      state.labStepSectionExpanded[sectionId] = !state.labStepSectionExpanded[sectionId];
      syncLabTestSections();
    });
  });

  el.transcriptionProvider.addEventListener("change", syncSettingsFieldState);
  el.finalSlideUpscaleMode.addEventListener("change", syncSettingsFieldState);

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

  for (const input of [
    el.transcriptionProvider,
    el.googleSpeechProjectId,
    el.googleSpeechLocation,
    el.googleSpeechModel,
    el.googleSpeechLanguageCodes,
  ]) {
    input.addEventListener("input", () => clearHealthStatus("transcription"));
    input.addEventListener("change", () => clearHealthStatus("transcription"));
  }

  for (const input of [el.runStepEdit, el.finalSlidePostprocessMode, el.geminiEditModel, el.geminiEditPrompt]) {
    input.addEventListener("input", () => clearHealthStatus("slideEdit"));
    input.addEventListener("change", () => clearHealthStatus("slideEdit"));
  }

  for (const input of [
    el.runStepTranslate,
    el.finalSlideTranslationMode,
    el.finalSlideTargetLanguageSearch,
    el.finalSlideTargetLanguage,
    el.geminiTranslateModel,
    el.geminiTranslatePrompt,
  ]) {
    input.addEventListener("input", () => clearHealthStatus("slideTranslate"));
    input.addEventListener("change", () => clearHealthStatus("slideTranslate"));
  }

  for (const input of [
    el.runStepUpscale,
    el.finalSlideUpscaleMode,
    el.finalSlideUpscaleModel,
    el.finalSlideUpscaleDevice,
    el.finalSlideUpscaleTileSize,
    el.finalSlideUpscaleTileOverlap,
    el.replicateNightmareRealesrganModelRef,
    el.replicateNightmareRealesrganVersionId,
    el.replicateNightmareRealesrganPricePerSecond,
  ]) {
    input.addEventListener("input", () => clearHealthStatus("slideUpscale"));
    input.addEventListener("change", () => clearHealthStatus("slideUpscale"));
  }

  for (const input of [
    el.runStepTextTranslate,
    el.finalSlideTargetLanguageSearch,
    el.finalSlideTargetLanguage,
    el.geminiTextTranslateModel,
    el.googleTranslateProjectId,
    el.googleTranslateLocation,
    el.googleTranslateSourceLanguageCode,
  ]) {
    input.addEventListener("input", () => clearHealthStatus("textTranslate"));
    input.addEventListener("change", () => clearHealthStatus("textTranslate"));
  }
  if (el.termbaseTableBody) {
    el.termbaseTableBody.addEventListener("input", () => clearHealthStatus("textTranslate"));
    el.termbaseTableBody.addEventListener("change", () => clearHealthStatus("textTranslate"));
  }

  for (const input of [
    el.googleTtsProjectId,
    el.finalSlideTargetLanguageSearch,
    el.finalSlideTargetLanguage,
    el.geminiTtsModel,
    el.geminiTtsVoice,
    el.geminiTtsPrompt,
  ]) {
    input.addEventListener("input", () => clearHealthStatus("tts"));
    input.addEventListener("change", () => clearHealthStatus("tts"));
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

  el.imageModalClose.addEventListener("click", closeImageModal);
  el.imageModalBackdrop.addEventListener("click", closeImageModal);
  el.statusModalClose.addEventListener("click", closeStatusModal);
  el.statusModalBackdrop.addEventListener("click", closeStatusModal);
  el.labStatusModalClose.addEventListener("click", closeLabStatusModal);
  el.labStatusModalBackdrop.addEventListener("click", closeLabStatusModal);
  el.roiStatusModalClose.addEventListener("click", closeRoiStatusModal);
  el.roiStatusModalBackdrop.addEventListener("click", closeRoiStatusModal);
  el.labImagePickerClose.addEventListener("click", closeLabImagePicker);
  el.labImagePickerBackdrop.addEventListener("click", closeLabImagePicker);
  el.labSettingsClose.addEventListener("click", closeLabSettingsModal);
  el.labSettingsBackdrop.addEventListener("click", closeLabSettingsModal);
  el.exportLabRunPickerClose.addEventListener("click", closeExportLabRunPicker);
  el.exportLabRunPickerBackdrop.addEventListener("click", closeExportLabRunPicker);
  el.exportLabSettingsClose.addEventListener("click", closeExportLabSettingsModal);
  el.exportLabSettingsBackdrop.addEventListener("click", closeExportLabSettingsModal);
  el.exportLabStatusModalClose.addEventListener("click", closeExportLabStatusModal);
  el.exportLabStatusModalBackdrop.addEventListener("click", closeExportLabStatusModal);
  el.videoPickerClose.addEventListener("click", closeVideoPicker);
  el.videoPickerBackdrop.addEventListener("click", closeVideoPicker);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && el.imageModal.classList.contains("open")) {
      closeImageModal();
    }
    if (e.key === "Escape" && el.statusModal.classList.contains("open")) {
      closeStatusModal();
    }
    if (e.key === "Escape" && el.labStatusModal.classList.contains("open")) {
      closeLabStatusModal();
    }
    if (e.key === "Escape" && el.roiStatusModal.classList.contains("open")) {
      closeRoiStatusModal();
    }
    if (e.key === "Escape" && el.labImagePickerModal.classList.contains("open")) {
      closeLabImagePicker();
    }
    if (e.key === "Escape" && el.labSettingsModal.classList.contains("open")) {
      closeLabSettingsModal();
    }
    if (e.key === "Escape" && el.exportLabRunPickerModal.classList.contains("open")) {
      closeExportLabRunPicker();
    }
    if (e.key === "Escape" && el.exportLabSettingsModal.classList.contains("open")) {
      closeExportLabSettingsModal();
    }
    if (e.key === "Escape" && el.exportLabStatusModal.classList.contains("open")) {
      closeExportLabStatusModal();
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
  state.runSlidesMode = el.runViewMode.value === "base" ? "base" : "final";
  state.runFinalSourceMode = ["raw", "translated"].includes(el.runFinalSourceMode.value)
    ? el.runFinalSourceMode.value
    : "processed";
  state.runFinalDisplayMode = el.runFinalDisplayMode.value === "compare" ? "compare" : "single";
  syncSettingsFieldState();
  syncLabActionState();
  syncExportLabActionState();
  setActiveTab(getInitialActiveTab());

  await runTask(() => loadConfig({ syncActionState }));
  initializeLabTestSettings();
  initializeExportLabTestSettings();
  await runTask(loadOverlay);
  await runTask(loadRuns);
  await runTask(loadLabStatus);
  await runTask(loadExportLabStatus);

  window.setInterval(pollCurrent, 2000);
  window.setInterval(() => {
    runTaskImmediate(loadLabStatus);
  }, 2000);
  window.setInterval(() => {
    runTaskImmediate(loadExportLabStatus);
  }, 2000);
}

init();
