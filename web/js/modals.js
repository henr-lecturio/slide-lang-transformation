import { el } from "./dom.js";
import { state } from "./state.js";
import { apiGet } from "./api.js";
import { showButtonSuccess } from "./ui-core.js";


const IMAGE_MODAL_MIN_SCALE = 1;
const IMAGE_MODAL_MAX_SCALE = 6;
const IMAGE_MODAL_ZOOM_FACTOR = 1.18;

let imageModalScale = IMAGE_MODAL_MIN_SCALE;
let imageModalOriginX = 50;
let imageModalOriginY = 50;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function applyImageModalZoom() {
  if (!el.imageModalImg) return;
  const scale = Number(imageModalScale.toFixed(3));
  el.imageModalImg.style.transformOrigin = `${imageModalOriginX.toFixed(2)}% ${imageModalOriginY.toFixed(2)}%`;
  el.imageModalImg.style.transform = `scale(${scale})`;
}

function resetImageModalZoom() {
  imageModalScale = IMAGE_MODAL_MIN_SCALE;
  imageModalOriginX = 50;
  imageModalOriginY = 50;
  applyImageModalZoom();
}

export function handleImageModalWheel(event) {
  if (!el.imageModal.classList.contains("open")) return;
  if (!el.imageModalImg.getAttribute("src")) return;
  event.preventDefault();

  const imageBounds = el.imageModalImg.getBoundingClientRect();
  if (imageBounds.width > 0 && imageBounds.height > 0) {
    imageModalOriginX = clamp(((event.clientX - imageBounds.left) / imageBounds.width) * 100, 0, 100);
    imageModalOriginY = clamp(((event.clientY - imageBounds.top) / imageBounds.height) * 100, 0, 100);
  }

  if (event.deltaY < 0) {
    imageModalScale = clamp(imageModalScale * IMAGE_MODAL_ZOOM_FACTOR, IMAGE_MODAL_MIN_SCALE, IMAGE_MODAL_MAX_SCALE);
  } else if (event.deltaY > 0) {
    imageModalScale = clamp(imageModalScale / IMAGE_MODAL_ZOOM_FACTOR, IMAGE_MODAL_MIN_SCALE, IMAGE_MODAL_MAX_SCALE);
  }
  if (Math.abs(imageModalScale - IMAGE_MODAL_MIN_SCALE) < 0.001) {
    imageModalScale = IMAGE_MODAL_MIN_SCALE;
  }
  applyImageModalZoom();
}

export function openStatusModal() {
  el.statusModal.classList.add("open");
  el.statusModal.setAttribute("aria-hidden", "false");
}

export function closeStatusModal() {
  el.statusModal.classList.remove("open");
  el.statusModal.setAttribute("aria-hidden", "true");
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
  resetImageModalZoom();
  const sep = url.includes("?") ? "&" : "?";
  el.imageModalImg.src = `${url}${sep}v=${Date.now()}`;
  el.imageModalCaption.textContent = name || "";
  el.imageModal.classList.add("open");
  el.imageModal.setAttribute("aria-hidden", "false");
}

export function closeImageModal() {
  resetImageModalZoom();
  el.imageModal.classList.remove("open");
  el.imageModal.setAttribute("aria-hidden", "true");
  el.imageModalImg.removeAttribute("src");
  el.imageModalCaption.textContent = "";
}

export function closeVideoPicker() {
  el.videoPickerModal.classList.remove("open");
  el.videoPickerModal.setAttribute("aria-hidden", "true");
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

