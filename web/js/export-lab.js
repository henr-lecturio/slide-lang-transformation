import { el } from "./dom.js";
import { state } from "./state.js";
import { apiGet, apiPost } from "./api.js";
import { formatRunIdLabel } from "./ui-core.js";

const EXPORT_LAB_TEST_SETTINGS_STORAGE_KEY = "slide-transform-export-lab-test-settings";

function setNodeText(node, text) {
  if (node) node.textContent = text;
}

function readExportLabSettingsFromStorage() {
  try {
    const raw = localStorage.getItem(EXPORT_LAB_TEST_SETTINGS_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function persistExportLabTestSettings() {
  try {
    localStorage.setItem(EXPORT_LAB_TEST_SETTINGS_STORAGE_KEY, JSON.stringify(state.exportLabTestSettings || {}));
  } catch {
    // ignore storage failures
  }
}

function defaultExportLabTestSettingsFromCurrentUi() {
  return {
    video_export_min_slide_sec: Number(el.videoExportMinSlideSec.value || 1.2),
    video_export_tail_pad_sec: Number(el.videoExportTailPadSec.value || 0.35),
    video_export_thumbnail_fade_sec: Number(el.videoExportThumbnailFadeSec.value || 0.3),
    video_export_intro_white_sec: Number(el.videoExportIntroWhiteSec.value || 1.0),
    video_export_intro_fade_sec: Number(el.videoExportIntroFadeSec.value || 0.4),
    video_export_intro_color: String(el.videoExportIntroColor.value || "white").trim(),
    video_export_outro_hold_sec: Number(el.videoExportOutroHoldSec.value || 1.5),
    video_export_outro_fade_sec: Number(el.videoExportOutroFadeSec.value || 1.5),
    video_export_outro_fade_color: String(el.videoExportOutroFadeColor.value || "black").trim(),
    video_export_outro_black_sec: Number(el.videoExportOutroBlackSec.value || 2.0),
    video_export_width: Number(el.videoExportWidth.value || 1920),
    video_export_height: Number(el.videoExportHeight.value || 1080),
    video_export_fps: Number(el.videoExportFps.value || 30),
    video_export_bg_color: String(el.videoExportBgColor.value || "white").trim(),
  };
}

function normalizeNumber(value, fallback, min = 0) {
  const num = Number(value);
  if (!Number.isFinite(num) || num < min) return fallback;
  return num;
}

function normalizeExportLabTestSettings(raw = {}) {
  const fallback = defaultExportLabTestSettingsFromCurrentUi();
  return {
    video_export_min_slide_sec: normalizeNumber(raw.video_export_min_slide_sec, fallback.video_export_min_slide_sec, 0.04),
    video_export_tail_pad_sec: normalizeNumber(raw.video_export_tail_pad_sec, fallback.video_export_tail_pad_sec, 0),
    video_export_thumbnail_fade_sec: normalizeNumber(raw.video_export_thumbnail_fade_sec, fallback.video_export_thumbnail_fade_sec, 0),
    video_export_intro_white_sec: normalizeNumber(raw.video_export_intro_white_sec, fallback.video_export_intro_white_sec, 0),
    video_export_intro_fade_sec: normalizeNumber(raw.video_export_intro_fade_sec, fallback.video_export_intro_fade_sec, 0),
    video_export_intro_color: String(raw.video_export_intro_color || fallback.video_export_intro_color || "white").trim(),
    video_export_outro_hold_sec: normalizeNumber(raw.video_export_outro_hold_sec, fallback.video_export_outro_hold_sec, 0),
    video_export_outro_fade_sec: normalizeNumber(raw.video_export_outro_fade_sec, fallback.video_export_outro_fade_sec, 0),
    video_export_outro_fade_color: String(raw.video_export_outro_fade_color || fallback.video_export_outro_fade_color || "black").trim(),
    video_export_outro_black_sec: normalizeNumber(raw.video_export_outro_black_sec, fallback.video_export_outro_black_sec, 0),
    video_export_width: normalizeNumber(raw.video_export_width, fallback.video_export_width, 1),
    video_export_height: normalizeNumber(raw.video_export_height, fallback.video_export_height, 1),
    video_export_fps: normalizeNumber(raw.video_export_fps, fallback.video_export_fps, 1),
    video_export_bg_color: String(raw.video_export_bg_color || fallback.video_export_bg_color || "white").trim(),
  };
}

function ensureExportLabTestSettings() {
  if (state.exportLabTestSettings) return state.exportLabTestSettings;
  state.exportLabTestSettings = normalizeExportLabTestSettings(
    readExportLabSettingsFromStorage() || defaultExportLabTestSettingsFromCurrentUi(),
  );
  persistExportLabTestSettings();
  return state.exportLabTestSettings;
}

function applyExportLabTestSettingsToForm() {
  ensureExportLabTestSettings();
  el.exportLabVideoExportMinSlideSec.value = state.exportLabTestSettings.video_export_min_slide_sec;
  el.exportLabVideoExportTailPadSec.value = state.exportLabTestSettings.video_export_tail_pad_sec;
  el.exportLabVideoExportThumbnailFadeSec.value = state.exportLabTestSettings.video_export_thumbnail_fade_sec;
  el.exportLabVideoExportIntroWhiteSec.value = state.exportLabTestSettings.video_export_intro_white_sec;
  el.exportLabVideoExportIntroFadeSec.value = state.exportLabTestSettings.video_export_intro_fade_sec;
  el.exportLabVideoExportIntroColor.value = state.exportLabTestSettings.video_export_intro_color;
  el.exportLabVideoExportOutroHoldSec.value = state.exportLabTestSettings.video_export_outro_hold_sec;
  el.exportLabVideoExportOutroFadeSec.value = state.exportLabTestSettings.video_export_outro_fade_sec;
  el.exportLabVideoExportOutroFadeColor.value = state.exportLabTestSettings.video_export_outro_fade_color;
  el.exportLabVideoExportOutroBlackSec.value = state.exportLabTestSettings.video_export_outro_black_sec;
  el.exportLabVideoExportWidth.value = state.exportLabTestSettings.video_export_width;
  el.exportLabVideoExportHeight.value = state.exportLabTestSettings.video_export_height;
  el.exportLabVideoExportFps.value = state.exportLabTestSettings.video_export_fps;
  el.exportLabVideoExportBgColor.value = state.exportLabTestSettings.video_export_bg_color;
}

function readExportLabTestSettingsFromForm() {
  state.exportLabTestSettings = normalizeExportLabTestSettings({
    video_export_min_slide_sec: el.exportLabVideoExportMinSlideSec.value,
    video_export_tail_pad_sec: el.exportLabVideoExportTailPadSec.value,
    video_export_thumbnail_fade_sec: el.exportLabVideoExportThumbnailFadeSec.value,
    video_export_intro_white_sec: el.exportLabVideoExportIntroWhiteSec.value,
    video_export_intro_fade_sec: el.exportLabVideoExportIntroFadeSec.value,
    video_export_intro_color: el.exportLabVideoExportIntroColor.value,
    video_export_outro_hold_sec: el.exportLabVideoExportOutroHoldSec.value,
    video_export_outro_fade_sec: el.exportLabVideoExportOutroFadeSec.value,
    video_export_outro_fade_color: el.exportLabVideoExportOutroFadeColor.value,
    video_export_outro_black_sec: el.exportLabVideoExportOutroBlackSec.value,
    video_export_width: el.exportLabVideoExportWidth.value,
    video_export_height: el.exportLabVideoExportHeight.value,
    video_export_fps: el.exportLabVideoExportFps.value,
    video_export_bg_color: el.exportLabVideoExportBgColor.value,
  });
  persistExportLabTestSettings();
  return state.exportLabTestSettings;
}

export function syncExportLabTestSections() {
  const sections = document.querySelectorAll(".step-section[data-export-lab-step-section]");
  for (const section of sections) {
    const sectionId = section.dataset.exportLabStepSection;
    const body = section.querySelector(".step-section-body");
    const toggleBtn = section.querySelector(".export-lab-step-section-toggle");
    if (!sectionId) continue;
    if (!(sectionId in state.exportLabStepSectionExpanded)) {
      state.exportLabStepSectionExpanded[sectionId] = false;
    }
    const expanded = Boolean(state.exportLabStepSectionExpanded[sectionId]);
    section.classList.toggle("is-open", expanded);
    if (body) {
      body.hidden = !expanded;
      body.setAttribute("aria-hidden", expanded ? "false" : "true");
    }
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", expanded ? "true" : "false");
    }
  }
}

export function initializeExportLabTestSettings() {
  ensureExportLabTestSettings();
  applyExportLabTestSettingsToForm();
  syncExportLabTestSections();
}

export function resetExportLabTestSettingsFromCurrentSettings() {
  state.exportLabTestSettings = normalizeExportLabTestSettings(defaultExportLabTestSettingsFromCurrentUi());
  persistExportLabTestSettings();
  applyExportLabTestSettingsToForm();
  syncExportLabTestSections();
}

export function saveExportLabTestSettings() {
  readExportLabTestSettingsFromForm();
  applyExportLabTestSettingsToForm();
  syncExportLabTestSections();
}

export function syncExportLabActionState() {
  const hasRun = Boolean(state.exportLabSelectedRun?.run_id);
  const isBusy = state.exportLabStatus === "running" || state.exportLabStatus === "stopping";
  el.exportLabPickRun.disabled = isBusy;
  el.exportLabOpenSettings.disabled = isBusy;
  el.exportLabRunExport.disabled = isBusy || !hasRun || !Boolean(state.exportLabSelectedRun?.export_ready);
  if (el.exportLabStopRun) {
    el.exportLabStopRun.disabled = state.exportLabStatus !== "running";
    el.exportLabStopRun.textContent = state.exportLabStatus === "stopping" ? "Stopping..." : "Stop Execution";
  }
}

export function renderExportLabSelection() {
  const selected = state.exportLabSelectedRun;
  const current = state.exportLabCurrent || null;
  if (!selected) {
    setNodeText(el.exportLabMeta, "No run selected.");
    el.exportLabDownloads.innerHTML = "";
    if (el.exportLabVideo) {
      el.exportLabVideo.removeAttribute("src");
      el.exportLabVideo.load();
    }
    syncExportLabActionState();
    return;
  }

  const parts = [
    formatRunIdLabel(selected.run_id),
    selected.run_status || "-",
    selected.image_dir_name ? `images=${selected.image_dir_name}` : "",
    selected.export_ready ? "export ready" : `missing=${(selected.missing_requirements || []).join(", ")}`,
  ].filter(Boolean);

  if (current?.status && current.status !== "idle") {
    parts.push(`job=${current.status}`);
  }
  setNodeText(el.exportLabMeta, parts.join(" | "));

  el.exportLabDownloads.innerHTML = "";
  const links = [
    { label: "MP4", url: current?.result_url || "" },
    { label: "Subtitles", url: current?.subtitle_url || "" },
    { label: "Timeline JSON", url: current?.timeline_json_url || "" },
    { label: "Timeline CSV", url: current?.timeline_csv_url || "" },
  ].filter((item) => item.url);
  if (links.length > 0) {
    for (const link of links) {
      const a = document.createElement("a");
      a.className = "summary-link";
      a.href = link.url;
      a.textContent = link.label;
      a.download = "";
      el.exportLabDownloads.appendChild(a);
    }
  }

  if (el.exportLabVideo) {
    if (current?.result_url) {
      const nextSrc = current.result_url;
      if (el.exportLabVideo.dataset.src !== nextSrc) {
        el.exportLabVideo.dataset.src = nextSrc;
        el.exportLabVideo.src = nextSrc;
        el.exportLabVideo.load();
      }
    } else {
      el.exportLabVideo.removeAttribute("src");
      delete el.exportLabVideo.dataset.src;
      el.exportLabVideo.load();
    }
  }

  syncExportLabActionState();
}

export function setExportLabStatus(current) {
  state.exportLabCurrent = current || null;
  state.exportLabStatus = current?.status || "idle";
  const logs = (current?.log_tail || []).slice(-120);
  const nextLog = logs.join("\n");
  if (el.exportLabLog && el.exportLabLog.textContent !== nextLog) {
    el.exportLabLog.textContent = nextLog;
    el.exportLabLog.scrollTop = el.exportLabLog.scrollHeight;
  }
  renderExportLabSelection();
}

export async function loadExportLabStatus() {
  const current = await apiGet("/api/export-lab/status");
  setExportLabStatus(current);
}

export async function stopExportLabJob() {
  const res = await apiPost("/api/export-lab/stop", {});
  setExportLabStatus(res.current || res);
}

export async function runExportLabAction() {
  if (!state.exportLabSelectedRun?.run_id) {
    throw new Error("Select a run in Export Lab first.");
  }
  const payload = {
    run_id: state.exportLabSelectedRun.run_id,
    settings: readExportLabTestSettingsFromForm(),
  };
  const res = await apiPost("/api/export-lab/export", payload);
  setExportLabStatus(res.current || res);
}
