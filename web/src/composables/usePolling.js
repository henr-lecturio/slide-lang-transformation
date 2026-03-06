import { onMounted, onUnmounted } from "vue";

export function usePolling(fn, ms = 2000) {
  let timerId = null;

  onMounted(() => {
    fn();
    timerId = window.setInterval(fn, ms);
  });

  onUnmounted(() => {
    if (timerId !== null) {
      window.clearInterval(timerId);
      timerId = null;
    }
  });
}
