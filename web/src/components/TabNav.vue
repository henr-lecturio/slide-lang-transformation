<template>
  <header class="topbar">
    <div class="topnav-row">
      <button class="topbar-logo" type="button" aria-label="Go to Control" @click="$emit('switch', 'home')">
        <img src="/lecturio_logo_white_transparent.png" alt="Lecturio" />
      </button>
      <div class="topnav-main">
        <nav class="topnav" aria-label="Primary">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            class="tab-btn"
            :class="{ active: activeTab === tab.key }"
            :data-tab="tab.key"
            type="button"
            @click="$emit('switch', tab.key)"
          >{{ tab.label }}</button>
        </nav>
        <button
          ref="saveBtn"
          v-show="activeTab === 'settings'"
          type="button"
          @click="$emit('save')"
        >Save Settings</button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref } from "vue";

const tabs = [
  { key: "home", label: "Control" },
  { key: "all-runs", label: "All Runs" },
  { key: "lab", label: "Lab" },
  { key: "roi", label: "ROI" },
  { key: "settings", label: "Settings" },
];

defineProps({
  activeTab: { type: String, default: "home" },
});

defineEmits(["switch", "save"]);

const saveBtn = ref(null);
defineExpose({ saveBtn });
</script>
