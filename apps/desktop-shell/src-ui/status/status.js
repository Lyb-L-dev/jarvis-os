const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

const elements = {
  shell: document.querySelector(".status-shell"),
  runtimeMode: document.querySelector("#runtime-mode"),
  overallDot: document.querySelector("#overall-dot"),
  title: document.querySelector("#page-title"),
  message: document.querySelector("#overall-message"),
  lastChecked: document.querySelector("#last-checked"),
  required: document.querySelector("#required-components"),
  optional: document.querySelector("#optional-components"),
  empty: document.querySelector("#empty-state"),
  selectedState: document.querySelector("#selected-state"),
  selectedName: document.querySelector("#selected-name"),
  selectedDetail: document.querySelector("#selected-detail"),
  selectedRecovery: document.querySelector("#selected-recovery"),
  refresh: document.querySelector("#refresh-button"),
  restart: document.querySelector("#restart-button"),
  logs: document.querySelector("#logs-button"),
  export: document.querySelector("#export-button"),
  releaseVersion: document.querySelector("#release-version"),
  schemaVersion: document.querySelector("#schema-version"),
  feedback: document.querySelector("#operation-feedback"),
};

const stateLabels = {
  ready: "就绪",
  degraded: "已降级",
  blocked: "已阻断",
  stopped: "已停止",
  not_configured: "未配置",
  idle: "等待启动",
  starting: "正在启动",
  stopping: "正在停止",
};

const modeLabels = {
  source: "源码适配器",
  bundled: "安装态运行时",
  unavailable: "运行适配器不可用",
  test: "测试运行时",
};

let diagnostics = null;
let selectedId = null;

function formatTime(value) {
  const date = new Date(Number(value));
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

function stateClass(state) {
  if (["ready", "degraded", "blocked"].includes(state)) return `status-${state}`;
  if (["idle", "starting", "stopping"].includes(state)) return "status-degraded";
  return "status-blocked";
}

function setFeedback(message, kind = "") {
  elements.feedback.textContent = message;
  elements.feedback.className = kind ? `is-${kind}` : "";
}

function setBusy(button, busy, label) {
  button.disabled = busy || (button === elements.restart && diagnostics?.runtimeMode === "unavailable");
  button.setAttribute("aria-busy", String(busy));
  const span = button.querySelector("span");
  if (!span.dataset.label) span.dataset.label = span.textContent;
  span.textContent = busy ? label : span.dataset.label;
}

function createCell(className, text) {
  const cell = document.createElement("span");
  cell.className = className;
  cell.setAttribute("role", "cell");
  cell.textContent = text;
  return cell;
}

function selectComponent(id, focus = false) {
  if (!diagnostics) return;
  const component = diagnostics.components.find((item) => item.id === id);
  if (!component) return;
  selectedId = id;
  document.querySelectorAll(".component-row").forEach((row) => {
    const selected = row.dataset.componentId === id;
    row.classList.toggle("is-selected", selected);
    row.setAttribute("aria-selected", String(selected));
    if (selected && focus) row.focus();
  });
  elements.selectedState.className = `selected-state state-${component.state}`;
  elements.selectedState.textContent = `${stateLabels[component.state] || component.state} · ${component.requirement === "required" ? "必需运行" : "可选能力"}`;
  elements.selectedName.textContent = component.name;
  elements.selectedDetail.textContent = component.detail;
  elements.selectedRecovery.hidden = !component.recovery;
  elements.selectedRecovery.textContent = component.recovery ? `恢复建议：${component.recovery}` : "";
}

function componentRow(component) {
  const row = document.createElement("div");
  row.className = "component-row";
  row.dataset.componentId = component.id;
  row.setAttribute("role", "row");
  row.setAttribute("tabindex", "0");
  row.setAttribute("aria-selected", "false");

  const name = document.createElement("span");
  name.className = "component-name";
  name.setAttribute("role", "cell");
  const strong = document.createElement("strong");
  strong.textContent = component.name;
  const requirement = document.createElement("span");
  requirement.textContent = component.requirement === "required" ? "必需运行" : "可选能力";
  name.append(strong, requirement);

  const state = createCell(`state-label state-${component.state}`, stateLabels[component.state] || component.state);
  const ownership = createCell("cell-copy", component.ownership === "app" ? "Jarvis 所有" : "外部依赖");
  const version = createCell("cell-mono", component.version || "—");
  const checked = createCell("cell-mono", formatTime(component.checkedAtMs));
  const reason = document.createElement("span");
  reason.className = "reason-copy";
  reason.setAttribute("role", "cell");
  const detail = document.createElement("span");
  detail.textContent = component.detail;
  reason.append(detail);
  if (component.recovery) {
    const recovery = document.createElement("small");
    recovery.textContent = component.recovery;
    reason.append(recovery);
  }
  row.append(name, state, ownership, version, checked, reason);
  row.addEventListener("click", () => selectComponent(component.id));
  row.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectComponent(component.id);
    }
  });
  return row;
}

function renderGroup(container, label, components) {
  container.replaceChildren();
  const heading = document.createElement("div");
  heading.className = "group-label";
  heading.setAttribute("role", "row");
  const headingCell = document.createElement("span");
  headingCell.setAttribute("role", "cell");
  headingCell.textContent = `${label} (${components.length})`;
  heading.append(headingCell);
  container.append(heading, ...components.map(componentRow));
}

function render(next) {
  diagnostics = next;
  document.querySelector(".evidence-panel").classList.remove("is-unavailable");
  const overallState = next.overall.state;
  elements.shell.classList.remove("status-ready", "status-degraded", "status-blocked");
  elements.shell.classList.add(stateClass(overallState));
  elements.overallDot.className = `state-dot ${stateClass(overallState)}`;
  elements.title.textContent = next.overall.title;
  elements.message.textContent = next.overall.message;
  elements.lastChecked.textContent = formatTime(next.generatedAtMs);
  elements.runtimeMode.textContent = modeLabels[next.runtimeMode] || next.runtimeMode;

  const required = next.components.filter((item) => item.requirement === "required");
  const optional = next.components.filter((item) => item.requirement === "optional");
  renderGroup(elements.required, "必需运行", required);
  renderGroup(elements.optional, "可选能力", optional);
  if (next.components.length === 0) {
    if (!elements.empty.isConnected) {
      elements.required.closest(".evidence-panel").append(elements.empty);
    }
    elements.empty.hidden = false;
  } else {
    elements.empty.remove();
  }

  const release = next.release;
  elements.releaseVersion.textContent = release?.app_version
    ? `Jarvis OS ${release.app_version} · ${release.channel || "local"}`
    : `Jarvis OS ${next.appVersion}`;
  elements.schemaVersion.textContent = release?.schema_revision
    ? `Schema ${release.schema_revision}`
    : "Schema 未记录";

  if (!selectedId || !next.components.some((item) => item.id === selectedId)) {
    selectedId = next.components.find((item) => item.state === "blocked")?.id
      || next.components.find((item) => item.state === "degraded")?.id
      || next.components[0]?.id;
  }
  if (selectedId) selectComponent(selectedId);
  elements.restart.disabled = next.runtimeMode === "unavailable";
}

function renderUnavailable(error) {
  diagnostics = null;
  selectedId = null;
  elements.shell.classList.remove("status-ready", "status-degraded");
  elements.shell.classList.add("status-blocked");
  elements.overallDot.className = "state-dot status-blocked";
  elements.title.textContent = "运行状态暂时不可用";
  elements.message.textContent = "无法从 Runtime Supervisor 读取当前证据；下方不会继续展示陈旧状态。请重新检查。";
  elements.lastChecked.textContent = formatTime(Date.now());
  elements.runtimeMode.textContent = "Supervisor 不可达";
  renderGroup(elements.required, "必需运行", []);
  renderGroup(elements.optional, "可选能力", []);
  if (!elements.empty.isConnected) {
    elements.required.closest(".evidence-panel").append(elements.empty);
  }
  elements.empty.hidden = false;
  elements.empty.querySelector("strong").textContent = "无法验证组件状态";
  elements.empty.querySelector("span").textContent = "已停止加载并清除陈旧证据；使用“重新检查”恢复。";
  document.querySelector(".evidence-panel").classList.add("is-unavailable");
  elements.selectedState.className = "selected-state state-blocked";
  elements.selectedState.textContent = "证据不可用";
  elements.selectedName.textContent = "Runtime Supervisor";
  elements.selectedDetail.textContent = String(error);
  elements.selectedRecovery.hidden = false;
  elements.selectedRecovery.textContent = "恢复建议：使用“重新检查”。如果持续失败，可打开日志目录。";
  elements.restart.disabled = true;
}

async function refresh({ announce = true } = {}) {
  setBusy(elements.refresh, true, "正在检查");
  if (announce) setFeedback("正在从 Runtime Supervisor 重新读取状态…");
  try {
    render(await invoke("runtime_diagnostics"));
    if (announce) setFeedback("已更新运行证据。", "success");
  } catch (error) {
    renderUnavailable(error);
    setFeedback(`无法读取运行证据：${String(error)}`, "error");
  } finally {
    setBusy(elements.refresh, false, "");
  }
}

async function invokeAction(button, command, busyLabel, successMessage) {
  setBusy(button, true, busyLabel);
  setFeedback(busyLabel);
  try {
    const result = await invoke(command);
    setFeedback(typeof successMessage === "function" ? successMessage(result) : successMessage, "success");
    await refresh({ announce: false });
  } catch (error) {
    setFeedback(`${busyLabel}失败：${String(error)}`, "error");
  } finally {
    setBusy(button, false, "");
  }
}

elements.refresh.addEventListener("click", () => refresh());
elements.restart.addEventListener("click", () => invokeAction(
  elements.restart,
  "runtime_restart_core",
  "正在重启 Jarvis Core",
  "Jarvis Core 重启流程已完成。",
));
elements.logs.addEventListener("click", () => invokeAction(
  elements.logs,
  "runtime_open_logs",
  "正在打开日志目录",
  (path) => `已打开日志目录：${path}`,
));
elements.export.addEventListener("click", () => invokeAction(
  elements.export,
  "runtime_export_diagnostics",
  "正在导出脱敏诊断",
  (result) => `脱敏诊断已生成：${result.path}`,
));

window.addEventListener("keydown", (event) => {
  if (event.key === "F5") {
    event.preventDefault();
    refresh();
  }
});

listen("runtime://snapshot", () => refresh({ announce: false }));
refresh({ announce: false });
