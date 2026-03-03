import { el } from "./dom.js";
import { state } from "./state.js";
import { apiGet, apiPost } from "./api.js";
import { formatUsd } from "./ui-core.js";
import { openImageModal } from "./modals.js";

export function syncLabActionState() {
  const hasImage = Boolean(state.labSelectedImage && state.labSelectedImage.image_url);
  const isBusy = state.labStatus === "running";
  el.labPickImage.disabled = isBusy;
  el.labRunEdit.disabled = isBusy || !hasImage;
  el.labRunTranslate.disabled = isBusy || !hasImage;
  el.labRunUpscale.disabled = isBusy || !hasImage;
}

export function renderLabSelection() {
  const item = state.labSelectedImage;
  if (!item) {
    el.labSelectedImage.textContent = "Kein Bild gewählt.";
    el.labOriginalImage.removeAttribute("src");
    el.labOriginalImage.onclick = null;
    syncLabActionState();
    return;
  }
  const metaText = `run=${item.run_id} | event=${item.event_id} | ${Number(item.slide_start || 0).toFixed(2)}s - ${Number(item.slide_end || 0).toFixed(2)}s | ${item.name}`;
  el.labSelectedImage.textContent = metaText;
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
  el.labJobStatus.textContent = `status: ${status}${action}${provider}${jobId}`;
  const resultMeta = [];
  if (current?.message) resultMeta.push(current.message);
  if (current?.input_name) resultMeta.push(`input=${current.input_name}`);
  if (current?.result_name) resultMeta.push(`result=${current.result_name}`);
  if (current?.estimated_cost_usd) resultMeta.push(`est_cost=${formatUsd(current.estimated_cost_usd)}`);
  el.labJobMeta.textContent = resultMeta.length > 0 ? resultMeta.join(" | ") : "Uses current Settings.";
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
    el.labSelectedImage.textContent = current.input_name
      ? `Letzter Testinput: ${current.input_name}`
      : "Letzter Testinput";
    el.labOriginalImage.src = `${current.original_url}?v=${Date.now()}`;
    el.labOriginalImage.onclick = () => openImageModal(current.original_url, current.input_name || "lab-input");
  }
  syncLabActionState();
}

export async function loadLabStatus() {
  const current = await apiGet("/api/lab/status");
  setLabStatus(current);
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
  };
  if (action === "upscale") {
    payload.provider = el.labUpscaleProvider.value;
  }
  const res = await apiPost(`/api/lab/${action}`, payload);
  setLabStatus(res.current || {});
}
