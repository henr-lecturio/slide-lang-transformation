import { createApp } from "vue";
import LabApp from "./LabApp.vue";

function mount() {
  const el = document.getElementById("lab-app");
  if (el) {
    createApp(LabApp).mount(el);
    return;
  }
  const observer = new MutationObserver(() => {
    const target = document.getElementById("lab-app");
    if (target) {
      observer.disconnect();
      createApp(LabApp).mount(target);
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
  setTimeout(() => {
    observer.disconnect();
    if (!document.getElementById("lab-app")) {
      console.warn("[lab-app] Mount point #lab-app not found after 10s, giving up.");
    }
  }, 10000);
}

mount();
