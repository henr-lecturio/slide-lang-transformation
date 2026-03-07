/**
 * Shared utility functions for style editor logic.
 * Used by StyleEditor.vue and ImageLabSettings.vue.
 */

export function parseStylesJson(jsonText) {
  const text = String(jsonText || "").trim();
  if (!text) return { version: 1, defaults: {}, roles: {}, slots: {} };
  try {
    const p = JSON.parse(text);
    return {
      version: Number(p?.version) > 0 ? Number(p.version) : 1,
      defaults: p && typeof p.defaults === "object" && p.defaults ? structuredClone(p.defaults) : {},
      roles: p && typeof p.roles === "object" && p.roles ? structuredClone(p.roles) : {},
      slots: p && typeof p.slots === "object" && p.slots ? structuredClone(p.slots) : {},
    };
  } catch {
    return { version: 1, defaults: {}, roles: {}, slots: {} };
  }
}

export function displayColor(style = {}) {
  const mode = String(style.text_color_mode ?? "").trim();
  const color = String(style.text_color ?? "").trim();
  if (mode === "fixed" && color) return color;
  if (color && color.toLowerCase() !== "auto") return color;
  return "auto";
}

export function displayPadding(style = {}) {
  const padding = String(style.padding ?? "").trim();
  if (padding) return padding;
  const top = style.box_padding_top_ratio ?? style.box_padding_y_ratio;
  const right = style.box_padding_right_ratio ?? style.box_padding_x_ratio;
  const bottom = style.box_padding_bottom_ratio ?? style.box_padding_y_ratio;
  const left = style.box_padding_left_ratio ?? style.box_padding_x_ratio;
  const values = [top, right, bottom, left].map((v) => (v === undefined || v === null || v === "" ? "" : String(v).trim()));
  if (values.every((v) => v !== "")) return values.join(" ");
  return "";
}

export function inferWeight(style = {}) {
  const explicit = String(style.font_weight ?? "").trim().toLowerCase();
  if (explicit === "medium") return "Medium";
  if (explicit === "bold") return "Bold";
  if (explicit === "regular") return "Regular";
  const fontPath = String(style.font_path ?? "").toLowerCase();
  if (fontPath.includes("bold")) return "Bold";
  if (fontPath.includes("medium")) return "Medium";
  return "Regular";
}

export function deletePaddingKeys(style) {
  delete style.padding;
  delete style.box_padding_x_ratio;
  delete style.box_padding_y_ratio;
  delete style.box_padding_top_ratio;
  delete style.box_padding_right_ratio;
  delete style.box_padding_bottom_ratio;
  delete style.box_padding_left_ratio;
}

export function normalizePadding(value) {
  const text = String(value ?? "").trim().replace(/,/g, " ");
  if (!text) return "";
  return text.split(/\s+/).filter(Boolean).join(" ");
}

export function parseIntOrUndef(value) {
  const text = String(value ?? "").trim();
  if (!text) return undefined;
  const num = Number(text);
  return Number.isFinite(num) ? Math.round(num) : undefined;
}

export function parseFloatOrUndef(value) {
  const text = String(value ?? "").trim();
  if (!text) return undefined;
  const num = Number(text);
  return Number.isFinite(num) ? num : undefined;
}

/**
 * Convert a style object to visible row values (weight, color, padding, etc.)
 */
export function styleToVisibleValues(style = {}) {
  return {
    font_weight: inferWeight(style),
    font_size: style.font_size == null ? "" : String(style.font_size),
    min_font_size: style.min_font_size == null ? "" : String(style.min_font_size),
    line_spacing_ratio: style.line_spacing_ratio == null ? "" : String(style.line_spacing_ratio),
    text_color: displayColor(style),
    padding: displayPadding(style),
  };
}
