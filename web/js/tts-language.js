import { el } from "./dom.js";
import { state } from "./state.js";
function normalizeLanguageSearch(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function getTtsLanguageOptions() {
  return Array.isArray(state.ttsLanguageOptions) ? state.ttsLanguageOptions : [];
}

function findTtsLanguageOptionByCode(code) {
  const wanted = String(code || "").trim();
  if (!wanted) return null;
  return getTtsLanguageOptions().find((item) => item.tts_language_code === wanted) || null;
}

function findTtsLanguageOptionByLabel(label) {
  const wanted = String(label || "").trim();
  if (!wanted) return null;
  return getTtsLanguageOptions().find((item) => item.label === wanted) || null;
}

export function getSelectedTtsLanguageOption() {
  return findTtsLanguageOptionByCode(el.finalSlideTargetLanguage.value);
}

function filteredTtsLanguageOptions(filterText = "") {
  const query = normalizeLanguageSearch(filterText);
  const all = getTtsLanguageOptions();
  if (!query) return all;
  return all.filter((item) => {
    const readiness = normalizeLanguageSearch(item.launch_readiness || "");
    const label = normalizeLanguageSearch(item.label || "");
    const code = normalizeLanguageSearch(item.tts_language_code || "");
    return label.includes(query) || code.includes(query) || readiness.includes(query);
  });
}

export function renderTtsLanguageOptions(filterText = "", preferredCode = "", preferredLabel = "") {
  const filtered = filteredTtsLanguageOptions(filterText);
  const previousCode = String(preferredCode || el.finalSlideTargetLanguage.value || "").trim();
  const previousLabel = String(preferredLabel || "").trim();
  el.finalSlideTargetLanguage.innerHTML = "";

  if (filtered.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No matching languages";
    el.finalSlideTargetLanguage.appendChild(option);
    el.finalSlideTargetLanguage.value = "";
    el.googleTtsLanguageCode.value = "";
    updateTtsLanguageHint();
    return;
  }

  for (const item of filtered) {
    const option = document.createElement("option");
    option.value = item.tts_language_code;
    option.textContent = item.launch_readiness
      ? `${item.label} [${item.tts_language_code}] (${item.launch_readiness})`
      : `${item.label} [${item.tts_language_code}]`;
    el.finalSlideTargetLanguage.appendChild(option);
  }

  const preferred = filtered.find((item) => item.tts_language_code === previousCode)
    || filtered.find((item) => item.label === previousLabel)
    || filtered[0];
  el.finalSlideTargetLanguage.value = preferred.tts_language_code;
  syncSelectedTtsLanguage();
}

export function syncSelectedTtsLanguage() {
  const selected = getSelectedTtsLanguageOption();
  el.googleTtsLanguageCode.value = selected ? selected.tts_language_code : "";
  updateTtsLanguageHint();
}

function setTtsLanguageHint(kind, text = "") {
  if (!el.ttsLanguageHint) return;
  el.ttsLanguageHint.className = `tts-language-hint muted is-${kind}`;
  el.ttsLanguageHint.textContent = text;
}

export function updateTtsLanguageHint() {
  if (!el.ttsLanguageHint) return;
  if (!el.runStepTts.checked) {
    setTtsLanguageHint("idle", "");
    return;
  }
  const selected = getSelectedTtsLanguageOption();
  if (!selected) {
    setTtsLanguageHint("warning", "Select a supported Gemini TTS language from the catalog.");
    return;
  }
  if (!el.runStepTextTranslate.checked) {
    setTtsLanguageHint(
      "note",
      `TTS will use ${selected.label} [${selected.tts_language_code}] for the source mapped text because Transcript Translate is disabled.`,
    );
    return;
  }
  const readiness = selected.launch_readiness ? ` | ${selected.launch_readiness}` : "";
  setTtsLanguageHint("ok", `Selected Gemini TTS language: ${selected.label} | ${selected.tts_language_code}${readiness}`);
}
