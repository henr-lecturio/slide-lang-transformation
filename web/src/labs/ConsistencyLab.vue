<template>
  <LabAccordion name="consistencyLab">
    <template #title>Consistency Lab</template>

    <LabToolbar
      :status="status"
      :has-selection="hasRun"
      idle-label="No run selected"
      @open-terminal="terminalOpen = true"
      @stop="stop"
    >
      <template #actions>
        <AppButton :disabled="isBusy" @click="openPicker">Select Run</AppButton>
        <AppButton :disabled="isBusy || !canReview" @click="runReview">Run Consistency Review</AppButton>
      </template>
    </LabToolbar>

    <div class="lab-preview-grid">
      <section class="lab-preview-panel">
        <div class="lab-preview-label-row">
          <div class="slide-compare-label">Consistency Report</div>
          <div class="muted lab-selection-meta">{{ selectionMeta }}</div>
        </div>
        <pre class="log consistency-lab-report">{{ reportText }}</pre>
      </section>
    </div>

    <PickerModal
      :open="pickerOpen"
      title="Select Run"
      :items="runs"
      :label-fn="runLabel"
      :item-key="(item) => item.run_id"
      :is-selected="(item) => item.run_id === selectedRun?.run_id"
      :is-disabled="(item) => !item.consistency_ready"
      empty-text="No runs with translated slides available."
      @close="pickerOpen = false"
      @select="selectRun"
    />

    <LogTerminal
      :open="terminalOpen"
      title="Consistency Lab Terminal"
      :logs="logs"
      @close="terminalOpen = false"
    />
  </LabAccordion>
</template>

<script setup>
import { ref, computed } from "vue";
import LabAccordion from "../components/LabAccordion.vue";
import AppButton from "../components/AppButton.vue";
import LabToolbar from "../components/LabToolbar.vue";
import PickerModal from "../components/PickerModal.vue";
import LogTerminal from "../components/LogTerminal.vue";
import { apiGet, apiPost } from "../composables/useApi.js";
import { useLabStatus } from "../composables/useLabStatus.js";
import { formatRunIdLabel } from "../stores/configStore.js";

const selectedRun = ref(null);
const runs = ref([]);
const reportText = ref("");
const pickerOpen = ref(false);
const terminalOpen = ref(false);
const reportRefreshKey = ref("");

const { status, currentData: current, logs, isBusy, setStatus, stop } = useLabStatus({
  faviconLabel: "consistency-lab",
  statusEndpoint: "/api/consistency-lab/status",
  stopEndpoint: "/api/consistency-lab/stop",
  fallbackPrefix: "Consistency Lab",
  onUpdate: () => renderReport(),
});

const hasRun = computed(() => Boolean(selectedRun.value?.run_id));
const canReview = computed(() => hasRun.value && Boolean(selectedRun.value?.consistency_ready));

const selectionMeta = computed(() => {
  if (!selectedRun.value) return "";
  return `| selected: ${formatRunIdLabel(selectedRun.value.run_id)}`;
});

function formatReport(report) {
  if (!report) return "";
  const lines = [];
  if (report.summary) {
    lines.push("=== Summary ===");
    lines.push(`Sequences found: ${report.summary.sequences_found ?? "-"}`);
    lines.push(`Slides checked: ${report.summary.slides_checked ?? "-"}`);
    lines.push(`Inconsistencies: ${report.summary.inconsistencies_found ?? "-"}`);
    lines.push(`Fixes applied: ${report.summary.fixes_applied ?? "-"}`);
    lines.push(`Fixes failed: ${report.summary.fixes_failed ?? "-"}`);
    lines.push("");
  }
  if (Array.isArray(report.sequences) && report.sequences.length > 0) {
    lines.push("=== Sequences ===");
    for (const seq of report.sequences) {
      lines.push(`Sequence: events ${(seq.event_ids || []).join(", ")}`);
      if (Array.isArray(seq.issues)) {
        for (const issue of seq.issues) {
          lines.push(`  - event ${issue.event_id}: ${issue.description || issue.type || "issue"}`);
          if (issue.fix_result) {
            lines.push(`    fix: ${issue.fix_result}`);
          }
        }
      }
      lines.push("");
    }
  }
  if (Array.isArray(report.glossary) && report.glossary.length > 0) {
    lines.push("=== Glossary ===");
    for (const entry of report.glossary) {
      lines.push(`  ${entry.source} -> ${entry.target}`);
    }
    lines.push("");
  }
  return lines.length > 0 ? lines.join("\n") : JSON.stringify(report, null, 2);
}

function renderReport() {
  const sel = selectedRun.value;
  const cur = current.value;
  const matchesSelection = Boolean(sel?.run_id && cur?.run_id && sel.run_id === cur.run_id);
  const visibleCurrent = matchesSelection ? cur : null;

  if (visibleCurrent?.status === "done" && visibleCurrent?.report_url) {
    const key = [visibleCurrent.job_id || "", visibleCurrent.status || "", visibleCurrent.finished_at || 0].join("|");
    if (reportRefreshKey.value !== key) {
      reportRefreshKey.value = key;
      reportText.value = "Loading report...";
      fetch(visibleCurrent.report_url, { cache: "no-store" })
        .then((res) => res.ok ? res.json() : null)
        .then((report) => {
          if (reportRefreshKey.value === key) {
            reportText.value = report ? formatReport(report) : "Report not available.";
          }
        })
        .catch(() => {
          if (reportRefreshKey.value === key) {
            reportText.value = "Failed to load report.";
          }
        });
    }
  } else {
    reportRefreshKey.value = "";
    reportText.value = "";
  }
}

async function openPicker() {
  try {
    const data = await apiGet("/api/consistency-lab/runs");
    runs.value = data.runs || [];
    if (data.current) {
      current.value = data.current;
    }
    if (!selectedRun.value && runs.value.length > 0) {
      const firstReady = runs.value.find((item) => item.consistency_ready) || runs.value[0];
      selectedRun.value = firstReady;
    }
    pickerOpen.value = true;
  } catch (err) {
    alert(err.message || String(err));
  }
}

function selectRun(item) {
  selectedRun.value = item;
  pickerOpen.value = false;
  renderReport();
}

async function runReview() {
  if (!selectedRun.value?.run_id) return;
  try {
    const payload = { run_id: selectedRun.value.run_id };
    const res = await apiPost("/api/consistency-lab/review", payload);
    setStatus(res.current || res);
  } catch (err) {
    alert(err.message || String(err));
  }
}

function runLabel(item) {
  const parts = [item.label || item.run_id, item.run_status || "-"];
  if (!item.consistency_ready && Array.isArray(item.missing_requirements) && item.missing_requirements.length > 0) {
    parts.push(`missing: ${item.missing_requirements.join(", ")}`);
  }
  return parts.join(" | ");
}

</script>
