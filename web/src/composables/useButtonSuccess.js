const timers = new WeakMap();

/**
 * Shows a success animation on a button element.
 * Adds the `.is-success` class and temporarily changes the button text,
 * then reverts after 1600ms.
 *
 * @param {HTMLButtonElement} btn - The button element
 * @param {string} [label="Saved"] - The success label to show
 */
export function showButtonSuccess(btn, label = "Saved") {
  if (!btn) return;
  const prev = timers.get(btn);
  if (prev) clearTimeout(prev);

  const originalText = btn.dataset.originalText || btn.textContent;
  btn.dataset.originalText = originalText;
  btn.textContent = label;
  btn.classList.add("is-success");
  btn.disabled = true;

  const tid = setTimeout(() => {
    btn.classList.remove("is-success");
    btn.textContent = originalText;
    btn.disabled = false;
    delete btn.dataset.originalText;
    timers.delete(btn);
  }, 1600);
  timers.set(btn, tid);
}
