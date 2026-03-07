import { createApp } from "vue";
import HealthApp from "./HealthApp.vue";

function mount() {
  const el = document.getElementById("health-app");
  if (el) {
    createApp(HealthApp).mount(el);
    return;
  }
  const observer = new MutationObserver(() => {
    const target = document.getElementById("health-app");
    if (target) {
      observer.disconnect();
      createApp(HealthApp).mount(target);
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

mount();
