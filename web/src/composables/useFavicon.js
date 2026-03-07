const BUSY_STATUSES = new Set(["running", "stopping"]);
const SPINNER_SIZE_PX = 32;
const SPINNER_INTERVAL_MS = 100;

const canvas = document.createElement("canvas");
canvas.width = SPINNER_SIZE_PX;
canvas.height = SPINNER_SIZE_PX;
const ctx = canvas.getContext("2d");

let linkEl = null;
let originalHref = "";
let originalType = "";
let timerId = 0;
let frame = 0;
let busy = false;

function ensureFaviconLink() {
  if (linkEl?.isConnected) {
    return linkEl;
  }
  linkEl = document.querySelector("link[rel~='icon']");
  if (!linkEl) {
    linkEl = document.createElement("link");
    linkEl.rel = "icon";
    linkEl.type = "image/png";
    linkEl.href = "/favicon.png";
    document.head.appendChild(linkEl);
  }
  if (!originalHref) {
    originalHref = linkEl.href || linkEl.getAttribute("href") || "/favicon.png";
  }
  if (!originalType) {
    originalType = linkEl.type || "image/png";
  }
  return linkEl;
}

function renderSpinnerFrame() {
  if (!ctx) return;
  const size = SPINNER_SIZE_PX;
  const center = size / 2;
  const radius = size * 0.32;
  const start = (frame * Math.PI) / 9;
  const sweep = Math.PI * 1.35;

  ctx.clearRect(0, 0, size, size);

  ctx.lineWidth = 3.5;
  ctx.strokeStyle = "rgba(120, 130, 145, 0.4)";
  ctx.beginPath();
  ctx.arc(center, center, radius, 0, Math.PI * 2);
  ctx.stroke();

  ctx.strokeStyle = "#1f8ef1";
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.arc(center, center, radius, start, start + sweep);
  ctx.stroke();

  const link = ensureFaviconLink();
  link.type = "image/png";
  link.href = canvas.toDataURL("image/png");
  frame = (frame + 1) % 36;
}

function startSpinner() {
  if (busy) return;
  busy = true;
  frame = 0;
  renderSpinnerFrame();
  timerId = window.setInterval(renderSpinnerFrame, SPINNER_INTERVAL_MS);
}

function stopSpinner() {
  if (!busy) return;
  busy = false;
  if (timerId) {
    window.clearInterval(timerId);
    timerId = 0;
  }
  const link = ensureFaviconLink();
  link.type = originalType || "image/png";
  link.href = originalHref || "/favicon.png";
}

const sources = new Map();

export function syncFavicon(source, status) {
  const normalized = String(status || "").trim().toLowerCase();
  sources.set(source, BUSY_STATUSES.has(normalized));
  const anyBusy = [...sources.values()].some(Boolean);
  if (anyBusy) {
    startSpinner();
  } else {
    stopSpinner();
  }
}
