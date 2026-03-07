<template>
  <div class="settings-row settings-row-inline">
    <div class="settings-key">{{ label }}</div>
    <div class="settings-value">
      <div class="settings-inline-actions">
        <button type="button" @click="runTest">{{ buttonLabel }}</button>
        <span :class="['health-check-status', `is-${status}`]" aria-live="polite">{{ statusText }}</span>
        <button
          class="health-meta-toggle"
          type="button"
          :aria-expanded="metaOpen ? 'true' : 'false'"
          :disabled="!meta"
          @click="metaOpen = !metaOpen"
        >
          <span class="step-section-chevron" aria-hidden="true"></span>
        </button>
      </div>
      <div v-if="metaOpen && meta" class="health-check-meta-wrap is-open">
        <div class="health-check-meta muted">{{ meta }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
  label: { type: String, required: true },
  buttonLabel: { type: String, required: true },
  endpoint: { type: String, required: true },
  payloadFn: { type: Function, required: true },
  formatMeta: { type: Function, required: true },
});

const status = ref("idle");
const statusText = ref("Not tested.");
const meta = ref("");
const metaOpen = ref(false);

async function runTest() {
  status.value = "pending";
  statusText.value = "Testing...";
  meta.value = "";
  metaOpen.value = false;

  try {
    const res = await fetch(props.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(props.payloadFn()),
    });
    const result = await res.json();

    if (result.ok) {
      status.value = "ok";
      statusText.value = "Reachable";
      meta.value = props.formatMeta(result);
    } else {
      status.value = "error";
      statusText.value = "Failed";
      meta.value = [result.error_type || "Error", result.error_message || result.message || "API check failed."]
        .filter(Boolean)
        .join(" | ");
    }
  } catch (err) {
    status.value = "error";
    statusText.value = "Failed";
    meta.value = err.message || String(err);
  }
}

function clear() {
  status.value = "idle";
  statusText.value = "Not tested.";
  meta.value = "";
  metaOpen.value = false;
}

function setIdle(text) {
  status.value = "idle";
  statusText.value = text;
  meta.value = "";
  metaOpen.value = false;
}

defineExpose({ clear, setIdle, statusText });
</script>
