import { ref, computed } from "vue";
import { apiGet, apiPost } from "./useApi.js";
import { usePolling } from "./usePolling.js";
import { syncFavicon } from "./useFavicon.js";

/**
 * Shared status/polling/log composable for all lab components.
 *
 * @param {Object} options
 * @param {string} options.faviconLabel    - e.g. "lab", "export-lab", "consistency-lab"
 * @param {string} options.statusEndpoint  - e.g. "/api/lab/status"
 * @param {string} [options.stopEndpoint]  - e.g. "/api/lab/stop"
 * @param {string} [options.fallbackPrefix] - e.g. "Export Lab" for empty-log fallback
 * @param {Function} [options.onUpdate]    - called after each setStatus(data) with the data
 */
export function useLabStatus({ faviconLabel, statusEndpoint, stopEndpoint, fallbackPrefix, onUpdate }) {
  const status = ref("idle");
  const currentData = ref(null);
  const logs = ref([]);

  const isBusy = computed(() => status.value === "running" || status.value === "stopping");

  function setStatus(data) {
    currentData.value = data || null;
    status.value = data?.status || "idle";
    syncFavicon(faviconLabel, data?.status || "idle");

    const logTail = (data?.log_tail || []).slice(-120);
    if (fallbackPrefix && logTail.length === 0 && data?.message) {
      logTail.push(`[${fallbackPrefix}] ${data.message}`);
    }
    logs.value = logTail;

    if (onUpdate) onUpdate(data);
  }

  async function loadStatus() {
    try {
      const data = await apiGet(statusEndpoint);
      setStatus(data);
    } catch { /* ignore polling errors */ }
  }

  async function stop() {
    if (!stopEndpoint) return;
    try {
      const res = await apiPost(stopEndpoint, {});
      setStatus(res.current || res);
    } catch (err) {
      alert(err.message || String(err));
    }
  }

  usePolling(loadStatus, 2000);

  return { status, currentData, logs, isBusy, setStatus, loadStatus, stop };
}
