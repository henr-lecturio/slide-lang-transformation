import { el } from "./dom.js";
import { state } from "./state.js";
import { apiGet } from "./api.js";
import { showButtonSuccess } from "./ui-core.js";

export function openStatusModal() {
  el.statusModal.classList.add("open");
  el.statusModal.setAttribute("aria-hidden", "false");
}

export function closeStatusModal() {
  el.statusModal.classList.remove("open");
  el.statusModal.setAttribute("aria-hidden", "true");
}

export function openLabStatusModal() {
  el.labStatusModal.classList.add("open");
  el.labStatusModal.setAttribute("aria-hidden", "false");
}

export function closeLabStatusModal() {
  el.labStatusModal.classList.remove("open");
  el.labStatusModal.setAttribute("aria-hidden", "true");
}

export function openExportLabStatusModal() {
  el.exportLabStatusModal.classList.add("open");
  el.exportLabStatusModal.setAttribute("aria-hidden", "false");
}

export function closeExportLabStatusModal() {
  el.exportLabStatusModal.classList.remove("open");
  el.exportLabStatusModal.setAttribute("aria-hidden", "true");
}

export function openRoiStatusModal() {
  el.roiStatusModal.classList.add("open");
  el.roiStatusModal.setAttribute("aria-hidden", "false");
}

export function closeRoiStatusModal() {
  el.roiStatusModal.classList.remove("open");
  el.roiStatusModal.setAttribute("aria-hidden", "true");
}

export function openImageModal(url, name) {
  const sep = url.includes("?") ? "&" : "?";
  el.imageModalImg.src = `${url}${sep}v=${Date.now()}`;
  el.imageModalCaption.textContent = name || "";
  el.imageModal.classList.add("open");
  el.imageModal.setAttribute("aria-hidden", "false");
}

export function closeImageModal() {
  el.imageModal.classList.remove("open");
  el.imageModal.setAttribute("aria-hidden", "true");
  el.imageModalImg.removeAttribute("src");
  el.imageModalCaption.textContent = "";
}

export function closeVideoPicker() {
  el.videoPickerModal.classList.remove("open");
  el.videoPickerModal.setAttribute("aria-hidden", "true");
}

export function closeExportLabRunPicker() {
  el.exportLabRunPickerModal.classList.remove("open");
  el.exportLabRunPickerModal.setAttribute("aria-hidden", "true");
}

export function closeLabImagePicker() {
  el.labImagePickerModal.classList.remove("open");
  el.labImagePickerModal.setAttribute("aria-hidden", "true");
}

export function openLabSettingsModal() {
  el.labSettingsModal.classList.add("open");
  el.labSettingsModal.setAttribute("aria-hidden", "false");
}

export function closeLabSettingsModal() {
  el.labSettingsModal.classList.remove("open");
  el.labSettingsModal.setAttribute("aria-hidden", "true");
}

export function openExportLabSettingsModal() {
  el.exportLabSettingsModal.classList.add("open");
  el.exportLabSettingsModal.setAttribute("aria-hidden", "false");
}

export function closeExportLabSettingsModal() {
  el.exportLabSettingsModal.classList.remove("open");
  el.exportLabSettingsModal.setAttribute("aria-hidden", "true");
}

function renderVideoPickerList({ runTask, saveConfig, successButton = null }) {
  const items = state.videoItems || [];
  el.videoPickerList.innerHTML = "";
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "No videos found under videos/.";
    el.videoPickerList.appendChild(empty);
    return;
  }

  for (const item of items) {
    if (item.type === "dir") {
      const dir = document.createElement("div");
      dir.className = "video-item video-dir";
      dir.style.paddingLeft = `${item.depth * 18}px`;
      dir.textContent = `[dir] ${item.path}`;
      el.videoPickerList.appendChild(dir);
      continue;
    }

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "video-item video-file";
    btn.style.paddingLeft = `${item.depth * 18 + 8}px`;
    btn.textContent = item.path;
    if (item.path === state.selectedVideoPath) {
      btn.classList.add("selected");
    }
    btn.addEventListener("click", () => runTask(async () => {
      state.selectedVideoPath = item.path;
      await saveConfig();
      closeVideoPicker();
      showButtonSuccess(successButton || el.pickVideo, "Selected");
    }));
    el.videoPickerList.appendChild(btn);
  }
}

export async function openVideoPicker({ runTask, saveConfig, successButton = null }) {
  const data = await apiGet("/api/videos");
  state.videoItems = data.items || [];
  if (data.selected_video) {
    state.selectedVideoPath = data.selected_video;
  }
  renderVideoPickerList({ runTask, saveConfig, successButton });
  el.videoPickerModal.classList.add("open");
  el.videoPickerModal.setAttribute("aria-hidden", "false");
}

function renderLabImagePickerList({ runTask, renderLabSelection }) {
  const items = state.labImages || [];
  el.labImagePickerList.innerHTML = "";
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "No final_slide_images found in the latest run.";
    el.labImagePickerList.appendChild(empty);
    return;
  }
  for (const item of items) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "video-item video-file";
    btn.textContent = `event ${item.event_id} | ${Number(item.slide_start || 0).toFixed(2)}s - ${Number(item.slide_end || 0).toFixed(2)}s | ${item.name}`;
    if (state.labSelectedImage && state.labSelectedImage.run_id === item.run_id && state.labSelectedImage.event_id === item.event_id) {
      btn.classList.add("selected");
    }
    btn.addEventListener("click", () => runTask(async () => {
      state.labSelectedImage = item;
      renderLabSelection();
      closeLabImagePicker();
      showButtonSuccess(el.labPickImage, "Selected");
    }));
    el.labImagePickerList.appendChild(btn);
  }
}

export async function openLabImagePicker({ runTask, renderLabSelection }) {
  const data = await apiGet("/api/lab/images");
  state.labImages = data.items || [];
  if (!state.labSelectedImage && state.labImages.length > 0) {
    state.labSelectedImage = state.labImages[0];
    renderLabSelection();
  }
  renderLabImagePickerList({ runTask, renderLabSelection });
  el.labImagePickerModal.classList.add("open");
  el.labImagePickerModal.setAttribute("aria-hidden", "false");
}

function renderExportLabRunPickerList({ runTask, renderExportLabSelection }) {
  const items = state.exportLabRuns || [];
  el.exportLabRunPickerList.innerHTML = "";
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "No exportable runs available.";
    el.exportLabRunPickerList.appendChild(empty);
    return;
  }
  for (const item of items) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "video-item video-file";
    if (state.exportLabSelectedRun?.run_id === item.run_id) {
      btn.classList.add("selected");
    }
    const parts = [item.label || item.run_id, item.run_status || "-"];
    if (!item.export_ready && Array.isArray(item.missing_requirements) && item.missing_requirements.length > 0) {
      parts.push(`missing: ${item.missing_requirements.join(", ")}`);
    }
    btn.textContent = parts.join(" | ");
    btn.title = btn.textContent;
    btn.disabled = !item.export_ready;
    btn.addEventListener("click", () => runTask(async () => {
      state.exportLabSelectedRun = item;
      renderExportLabSelection();
      closeExportLabRunPicker();
      showButtonSuccess(el.exportLabPickRun, "Selected");
    }));
    el.exportLabRunPickerList.appendChild(btn);
  }
}

export async function openExportLabRunPicker({ runTask, renderExportLabSelection }) {
  const data = await apiGet("/api/export-lab/runs");
  state.exportLabRuns = data.runs || [];
  if (data.current) {
    state.exportLabCurrent = data.current;
  }
  if (!state.exportLabSelectedRun && state.exportLabRuns.length > 0) {
    const firstReady = state.exportLabRuns.find((item) => item.export_ready) || state.exportLabRuns[0];
    state.exportLabSelectedRun = firstReady;
    renderExportLabSelection();
  }
  renderExportLabRunPickerList({ runTask, renderExportLabSelection });
  el.exportLabRunPickerModal.classList.add("open");
  el.exportLabRunPickerModal.setAttribute("aria-hidden", "false");
}
