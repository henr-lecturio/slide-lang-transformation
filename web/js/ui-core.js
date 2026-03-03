import { el } from "./dom.js";

const ACTIVE_TAB_STORAGE_KEY = "slide-transform-active-tab";
const buttonFeedbackTimers = new WeakMap();

export function videoThumbUrl(videoPath) {
  return `/api/videos/thumbnail?path=${encodeURIComponent(videoPath)}&v=${Date.now()}`;
}

export function formatUsd(value) {
  const num = Number(value || 0);
  if (!(num > 0)) return "-";
  return `$${num.toFixed(4)}`;
}

export function formatRunIdLabel(runId) {
  const raw = String(runId || "").trim();
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})(?:-(\d{2}))?$/);
  if (!match) return raw || "-";

  const [, year, month, day, hour, minute] = match;
  const monthNames = {
    "01": "Jan",
    "02": "Feb",
    "03": "Mar",
    "04": "Apr",
    "05": "May",
    "06": "Jun",
    "07": "Jul",
    "08": "Aug",
    "09": "Sep",
    "10": "Oct",
    "11": "Nov",
    "12": "Dec",
  };
  const monthLabel = monthNames[month] || month;
  return `${day}-${monthLabel}-${year}, ${hour}:${minute}`;
}

export function syncSettingsKeyTooltips() {
  document.querySelectorAll(".settings-key").forEach((node) => {
    const text = (node.textContent || "").trim();
    if (text) {
      node.setAttribute("title", text);
    } else {
      node.removeAttribute("title");
    }
  });
}

export function setActiveTab(tabName) {
  const allowedTabs = new Set(["home", "all-runs", "image-lab", "roi", "settings"]);
  const nextTab = allowedTabs.has(tabName) ? tabName : "home";
  for (const btn of el.tabButtons) {
    const active = btn.dataset.tab === nextTab;
    btn.classList.toggle("active", active);
  }
  el.panelHome.classList.toggle("active", nextTab === "home");
  el.panelAllRuns.classList.toggle("active", nextTab === "all-runs");
  el.panelImageLab.classList.toggle("active", nextTab === "image-lab");
  el.panelRoi.classList.toggle("active", nextTab === "roi");
  el.panelSettings.classList.toggle("active", nextTab === "settings");
  if (el.saveSettings) {
    el.saveSettings.classList.toggle("hidden", nextTab !== "settings");
  }
  try {
    window.localStorage.setItem(ACTIVE_TAB_STORAGE_KEY, nextTab);
  } catch {
    // Ignore storage failures and keep runtime behavior intact.
  }
}

export function getInitialActiveTab() {
  try {
    const stored = window.localStorage.getItem(ACTIVE_TAB_STORAGE_KEY) || "";
    if (["home", "all-runs", "image-lab", "roi", "settings"].includes(stored)) {
      return stored;
    }
  } catch {
    // Ignore storage failures and fall back to home.
  }
  return "home";
}

export function showButtonSuccess(button, successLabel, message = "") {
  if (!button) return;
  const existingTimer = buttonFeedbackTimers.get(button);
  if (existingTimer) {
    window.clearTimeout(existingTimer);
  }

  const originalText = button.dataset.originalText || button.textContent;
  button.dataset.originalText = originalText;
  button.textContent = successLabel;
  button.classList.add("is-success");
  if (message) {
    el.configMeta.textContent = message;
  }

  const timer = window.setTimeout(() => {
    button.textContent = button.dataset.originalText || originalText;
    button.classList.remove("is-success");
    buttonFeedbackTimers.delete(button);
  }, 1600);
  buttonFeedbackTimers.set(button, timer);
}
