import { el } from "./dom.js";
import { state } from "./state.js";
import { apiGet, apiPost } from "./api.js";
import { formatRunIdLabel } from "./ui-core.js";

function setNodeText(node, text) {
  if (node) node.textContent = text;
}

function formatConsistencyLabStatus(status, hasSelection) {
  switch (status) {
    case "running":
      return { label: "Running", iconClass: "is-running", lineClass: "is-running" };
    case "stopping":
      return { label: "Stopping", iconClass: "is-running", lineClass: "is-running" };
    case "done":
      return { label: "Done", iconClass: "is-done", lineClass: "is-done" };
    case "error":
      return { label: "Error", iconClass: "is-error", lineClass: "is-error" };
    case "stopped":
      return { label: "Stopped", iconClass: "is-stopped", lineClass: "is-stopped" };
  }
  if (!hasSelection) {
    return { label: "No run selected", iconClass: "", lineClass: "is-idle" };
  }
  return { label: "Ready", iconClass: "", lineClass: "is-ready" };
}

function renderConsistencyLabMeta(current, selected) {
  if (!el.consistencyLabMeta) return;
  const meta = formatConsistencyLabStatus(current?.status || "idle", Boolean(selected));
  el.consistencyLabMeta.className = `export-lab-status-line lab-toolbar-status ${meta.lineClass}`;
  el.consistencyLabMeta.innerHTML = "";
  const chip = document.createElement("div");
  chip.className = "export-lab-status-chip";
  const icon = document.createElement("span");
  icon.className = meta.iconClass ? `step-icon ${meta.iconClass}` : "step-icon";
  icon.setAttribute("aria-hidden", "true");
  const label = document.createElement("span");
  label.className = "export-lab-status-label";
  label.textContent = meta.label;
  chip.append(icon, label);
  el.consistencyLabMeta.appendChild(chip);
}

function formatReport(report) {
  if (!report) return "";
  const lines = [];
  if (report.summary) {
    lines.push(`=== Summary ===`);
    lines.push(`Sequences found: ${report.summary.sequences_found ?? "-"}`);
    lines.push(`Slides checked: ${report.summary.slides_checked ?? "-"}`);
    lines.push(`Inconsistencies: ${report.summary.inconsistencies_found ?? "-"}`);
    lines.push(`Fixes applied: ${report.summary.fixes_applied ?? "-"}`);
    lines.push(`Fixes failed: ${report.summary.fixes_failed ?? "-"}`);
    lines.push("");
  }
  if (Array.isArray(report.sequences) && report.sequences.length > 0) {
    lines.push(`=== Sequences ===`);
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
    lines.push(`=== Glossary ===`);
    for (const entry of report.glossary) {
      lines.push(`  ${entry.source} -> ${entry.target}`);
    }
    lines.push("");
  }
  return lines.length > 0 ? lines.join("\n") : JSON.stringify(report, null, 2);
}

export function syncConsistencyLabActionState() {
  const hasRun = Boolean(state.consistencyLabSelectedRun?.run_id);
  const isBusy = state.consistencyLabStatus === "running" || state.consistencyLabStatus === "stopping";
  el.consistencyLabPickRun.disabled = isBusy;
  el.consistencyLabRunReview.disabled = isBusy || !hasRun || !Boolean(state.consistencyLabSelectedRun?.consistency_ready);
  if (el.consistencyLabStopRun) {
    el.consistencyLabStopRun.disabled = state.consistencyLabStatus !== "running";
    el.consistencyLabStopRun.textContent = state.consistencyLabStatus === "stopping" ? "Stopping..." : "Stop Execution";
  }
}

export function renderConsistencyLabSelection() {
  const selected = state.consistencyLabSelectedRun;
  const current = state.consistencyLabCurrent || null;
  const currentMatchesSelection = Boolean(
    selected?.run_id
      && current?.run_id
      && selected.run_id === current.run_id,
  );
  const visibleCurrent = currentMatchesSelection ? current : null;
  if (!selected) {
    setNodeText(el.consistencyLabSelectedRun, "");
    renderConsistencyLabMeta(current, null);
    if (el.consistencyLabReport) el.consistencyLabReport.textContent = "";
    syncConsistencyLabActionState();
    return;
  }

  setNodeText(el.consistencyLabSelectedRun, `| selected: ${formatRunIdLabel(selected.run_id)}`);
  renderConsistencyLabMeta(visibleCurrent, selected);

  if (el.consistencyLabReport) {
    if (visibleCurrent?.status === "done" && visibleCurrent?.report_url) {
      const refreshKey = [
        visibleCurrent.job_id || "",
        visibleCurrent.status || "",
        visibleCurrent.finished_at || 0,
      ].join("|");
      if (el.consistencyLabReport.dataset.refreshKey !== refreshKey) {
        el.consistencyLabReport.dataset.refreshKey = refreshKey;
        el.consistencyLabReport.textContent = "Loading report...";
        fetch(visibleCurrent.report_url, { cache: "no-store" })
          .then((res) => res.ok ? res.json() : null)
          .then((report) => {
            if (el.consistencyLabReport.dataset.refreshKey === refreshKey) {
              el.consistencyLabReport.textContent = report ? formatReport(report) : "Report not available.";
            }
          })
          .catch(() => {
            if (el.consistencyLabReport.dataset.refreshKey === refreshKey) {
              el.consistencyLabReport.textContent = "Failed to load report.";
            }
          });
      }
    } else {
      delete el.consistencyLabReport.dataset.refreshKey;
      el.consistencyLabReport.textContent = "";
    }
  }

  syncConsistencyLabActionState();
}

export function setConsistencyLabStatus(current) {
  state.consistencyLabCurrent = current || null;
  state.consistencyLabStatus = current?.status || "idle";
  const logs = (current?.log_tail || []).slice(-120);
  if (logs.length === 0 && current?.message) {
    logs.push(`[Consistency Lab] ${current.message}`);
  }
  const nextLog = logs.join("\n");
  if (el.consistencyLabLog && el.consistencyLabLog.textContent !== nextLog) {
    el.consistencyLabLog.textContent = nextLog;
    el.consistencyLabLog.scrollTop = el.consistencyLabLog.scrollHeight;
  }
  renderConsistencyLabSelection();
}

export async function loadConsistencyLabStatus() {
  const current = await apiGet("/api/consistency-lab/status");
  setConsistencyLabStatus(current);
}

export async function stopConsistencyLabJob() {
  const res = await apiPost("/api/consistency-lab/stop", {});
  setConsistencyLabStatus(res.current || res);
}

export async function runConsistencyLabAction() {
  if (!state.consistencyLabSelectedRun?.run_id) {
    throw new Error("Select a run in Consistency Lab first.");
  }
  const payload = { run_id: state.consistencyLabSelectedRun.run_id };
  const res = await apiPost("/api/consistency-lab/review", payload);
  setConsistencyLabStatus(res.current || res);
}
