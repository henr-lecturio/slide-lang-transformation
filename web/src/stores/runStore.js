import { reactive } from "vue";
import { apiGet, apiPost } from "../composables/useApi.js";
import { formatRunIdLabel, formatUsd } from "./configStore.js";
import { syncFavicon } from "../composables/useFavicon.js";

export const runStore = reactive({
  currentRunId: null,
  currentRunStatus: "idle",
  currentRunSteps: [],
  logTail: [],

  latestRunId: null,
  latestRunDetail: null,

  selectedRunId: null,
  selectedRunDetail: null,

  runs: [],

  latestInfoExpanded: false,
  latestSlidesMode: "final",
  latestFinalSourceMode: "processed",
  latestFinalDisplayMode: "single",
  latestShowOriginalText: true,

  runSlidesMode: "final",
  runFinalSourceMode: "processed",
  runFinalDisplayMode: "single",
  runShowOriginalText: true,

  lastSettledRefreshKey: "",
});

function preferredLatestRunId(runs, current) {
  const currentRunId = current?.run_id || "";
  const currentStatus = current?.status || "";
  if (currentRunId && currentStatus && currentStatus !== "idle") {
    return currentRunId;
  }
  return runs.length > 0 ? runs[0].id : null;
}

function settledRefreshKey(current) {
  const status = current?.status || "";
  if (!["done", "error", "stopped"].includes(status)) return "";
  const runId = current?.run_id || "";
  const finishedAt = current?.finished_at || "";
  const exitCode = current?.exit_code ?? "";
  return `${status}|${runId}|${finishedAt}|${exitCode}`;
}

export function setStatus(current) {
  const status = current.status || "idle";
  runStore.currentRunStatus = status;
  syncFavicon("run", status);
  runStore.currentRunId = current.run_id || null;
  runStore.currentRunSteps = Array.isArray(current?.steps) ? current.steps : [];
  runStore.logTail = (current.log_tail || []).slice(-120);
}

export async function loadLatestRunDetails() {
  const runId = runStore.latestRunId;
  if (!runId) {
    runStore.latestRunDetail = null;
    return;
  }
  const detail = await apiGet(`/api/runs/${encodeURIComponent(runId)}`);
  runStore.latestRunDetail = detail;
}

export async function loadSelectedRunDetails() {
  const runId = runStore.selectedRunId;
  if (!runId) {
    runStore.selectedRunDetail = null;
    return;
  }
  const detail = await apiGet(`/api/runs/${encodeURIComponent(runId)}`);
  runStore.selectedRunDetail = detail;
}

export async function loadRuns() {
  const data = await apiGet("/api/runs");
  const current = data.current || {};
  setStatus(current);
  const currentSettledKey = settledRefreshKey(current);
  if (currentSettledKey) {
    runStore.lastSettledRefreshKey = currentSettledKey;
  }
  const runs = data.runs || [];
  runStore.runs = runs;
  runStore.latestRunId = preferredLatestRunId(runs, current);
  const prev = runStore.selectedRunId;
  if (runs.length === 0) {
    runStore.selectedRunId = null;
    runStore.latestRunDetail = null;
    runStore.selectedRunDetail = null;
    return;
  }
  const fallback = runs[0].id;
  runStore.selectedRunId = runs.some((r) => r.id === prev) ? prev : fallback;
  await loadLatestRunDetails();
  await loadSelectedRunDetails();
}

export async function startRun() {
  await apiPost("/api/runs", {});
  await loadRuns();
}

export async function stopRun() {
  await apiPost("/api/runs/stop", {});
  const current = await apiGet("/api/runs/current");
  setStatus(current);
}

export async function retryRun() {
  await apiPost("/api/runs/retry", {});
  await loadRuns();
}

export async function pollCurrent() {
  try {
    const current = await apiGet("/api/runs/current");
    setStatus(current);
    if (current.run_id && ["running", "stopping"].includes(current.status || "")) {
      runStore.latestRunId = current.run_id;
      await loadLatestRunDetails();
    }
    const key = settledRefreshKey(current);
    if (key && key !== runStore.lastSettledRefreshKey) {
      runStore.lastSettledRefreshKey = key;
      await loadRuns();
    }
  } catch (err) {
    console.error(err);
  }
}

export async function setFinalSlideImageMode(runId, eventId, mode) {
  await apiPost(`/api/runs/${encodeURIComponent(runId)}/final-slide-image-mode`, {
    event_id: eventId,
    mode,
  });
}

// --- Image resolution helpers ---

export function resolveRenderedFinalImage(item, slideSourceMode) {
  const wantsRaw = slideSourceMode === "raw";
  const wantsTranslated = slideSourceMode === "translated";

  if (wantsRaw && item.raw_slide_image_url) {
    return { url: item.raw_slide_image_url, name: item.raw_slide_image_name || item.image_name || "", slideSourceLabel: "raw", resolutionLabel: "native" };
  }
  if (wantsTranslated && item.translated_upscaled_slide_image_url) {
    return { url: item.translated_upscaled_slide_image_url, name: item.translated_upscaled_slide_image_name || item.image_name || "", slideSourceLabel: "translated", resolutionLabel: "x4" };
  }
  if (wantsTranslated && item.translated_slide_image_url) {
    return { url: item.translated_slide_image_url, name: item.translated_slide_image_name || item.image_name || "", slideSourceLabel: "translated", resolutionLabel: "native" };
  }
  if (item.processed_upscaled_slide_image_url) {
    return { url: item.processed_upscaled_slide_image_url, name: item.processed_upscaled_slide_image_name || item.image_name || "", slideSourceLabel: "processed", resolutionLabel: "x4" };
  }
  if (item.image_mode === "full") {
    return { url: item.full_image_url || item.image_url || "", name: item.full_image_name || item.image_name || "", slideSourceLabel: wantsTranslated ? "translated" : "processed", resolutionLabel: "native" };
  }
  if (item.processed_slide_image_url) {
    return { url: item.processed_slide_image_url, name: item.processed_slide_image_name || item.image_name || "", slideSourceLabel: "processed", resolutionLabel: "native" };
  }
  if (item.raw_slide_image_url) {
    return { url: item.raw_slide_image_url, name: item.raw_slide_image_name || item.image_name || "", slideSourceLabel: "raw", resolutionLabel: "native" };
  }
  return { url: item.image_url || "", name: item.image_name || "", slideSourceLabel: item.image_mode === "slide" ? "processed" : "-", resolutionLabel: "native" };
}

function resolveRenderedFinalImageStrict(item, sourceLabel, resolutionMode) {
  if (sourceLabel === "raw") {
    if (resolutionMode === "native" && item.raw_slide_image_url) {
      return { url: item.raw_slide_image_url, name: item.raw_slide_image_name || item.image_name || "", slideSourceLabel: "raw", resolutionLabel: "native" };
    }
    return { url: "", name: "", slideSourceLabel: "raw", resolutionLabel: resolutionMode };
  }
  if (sourceLabel === "translated") {
    if (resolutionMode === "native" && item.translated_slide_image_url) {
      return { url: item.translated_slide_image_url, name: item.translated_slide_image_name || item.image_name || "", slideSourceLabel: "translated", resolutionLabel: "native" };
    }
    if (resolutionMode === "native" && item.image_mode === "full" && item.full_image_url) {
      return { url: item.full_image_url, name: item.full_image_name || item.image_name || "", slideSourceLabel: "translated", resolutionLabel: "native" };
    }
    if (resolutionMode === "x4" && item.translated_upscaled_slide_image_url) {
      return { url: item.translated_upscaled_slide_image_url, name: item.translated_upscaled_slide_image_name || item.image_name || "", slideSourceLabel: "translated", resolutionLabel: "x4" };
    }
    return { url: "", name: "", slideSourceLabel: "translated", resolutionLabel: resolutionMode };
  }
  if (resolutionMode === "native" && item.processed_slide_image_url) {
    return { url: item.processed_slide_image_url, name: item.processed_slide_image_name || item.image_name || "", slideSourceLabel: "processed", resolutionLabel: "native" };
  }
  if (resolutionMode === "native" && item.image_mode === "full" && item.full_image_url) {
    return { url: item.full_image_url, name: item.full_image_name || item.image_name || "", slideSourceLabel: "processed", resolutionLabel: "native" };
  }
  if (resolutionMode === "x4" && item.processed_upscaled_slide_image_url) {
    return { url: item.processed_upscaled_slide_image_url, name: item.processed_upscaled_slide_image_name || item.image_name || "", slideSourceLabel: "processed", resolutionLabel: "x4" };
  }
  return { url: "", name: "", slideSourceLabel: "processed", resolutionLabel: resolutionMode };
}

export function resolveCompareRenderedImages(item, slideSourceMode) {
  const left = resolveRenderedFinalImageStrict(item, slideSourceMode, "native");
  if (left.slideSourceLabel === "raw") {
    return { left, right: { url: "", name: "", slideSourceLabel: "raw", resolutionLabel: "x4", missingReason: "x4 is not available for raw" } };
  }
  const right = resolveRenderedFinalImageStrict(item, left.slideSourceLabel, "x4");
  if (right.url) return { left, right };
  return { left, right: { ...right, missingReason: `No x4 image available for ${left.slideSourceLabel}` } };
}

export function deriveLatestAutoPreview(detail) {
  if (!detail) return null;
  if (detail.translated_upscaled_slides_ready) {
    return { slidesMode: "final", sourceMode: "translated" };
  }
  if (detail.upscaled_slides_ready) {
    return { slidesMode: "final", sourceMode: "processed" };
  }
  if (detail.translated_slides_ready) {
    return { slidesMode: "final", sourceMode: "translated" };
  }
  if (detail.final_slides_ready) {
    return { slidesMode: "final", sourceMode: "processed" };
  }
  if (detail.base_events_ready) {
    return { slidesMode: "base", sourceMode: "processed" };
  }
  return null;
}

export function shouldAutoPreviewLatest(detail) {
  const status = detail?.run_status || "";
  return ["running", "done", "error", "stopped"].includes(status);
}

export function getDownloadLinks(detail, { includeVideo = true, includeNonVideo = true } = {}) {
  if (!detail) return [];
  return [
    ...(includeNonVideo ? [
      { label: "Translated Text JSON", url: detail.translated_text_json_url, name: "slide_text_map_final_translated.json" },
      { label: "Translated Text CSV", url: detail.translated_text_csv_url, name: "slide_text_map_final_translated.csv" },
      { label: "TTS Manifest", url: detail.tts_manifest_url, name: "tts_manifest.json" },
      { label: "TTS Full Audio", url: detail.tts_full_audio_url, name: "full_transcript.wav" },
      { label: "TTS Alignment JSON", url: detail.tts_alignment_json_url, name: "segment_alignment.json" },
      { label: "TTS Alignment CSV", url: detail.tts_alignment_csv_url, name: "segment_alignment.csv" },
      { label: "Timeline JSON", url: detail.video_timeline_json_url, name: "timeline.json" },
      { label: "Timeline CSV", url: detail.video_timeline_csv_url, name: "timeline.csv" },
    ] : []),
    ...(includeVideo ? [
      { label: "Subtitles", url: detail.exported_srt_url, name: detail.exported_video_name ? detail.exported_video_name.replace(/\.mp4$/i, ".srt") : "final.srt" },
      { label: "MP4", url: detail.exported_video_url, name: detail.exported_video_name || "final.mp4" },
    ] : []),
  ].filter((item) => item.url);
}
