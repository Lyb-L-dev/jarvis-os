const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

const stageElement = document.querySelector("#runtime-stage");
const messageElement = document.querySelector("#runtime-message");
const elapsedElement = document.querySelector("#elapsed");
const errorActions = document.querySelector("#error-actions");
const errorCode = document.querySelector("#error-code");
const retryButton = document.querySelector("#retry-button");
const stageItems = [...document.querySelectorAll("[data-stage]")];
const setupPanel = document.querySelector("#setup-panel");
const statusCard = document.querySelector("#status-card");
const stageList = document.querySelector(".stage-list");
const migrationSource = document.querySelector("#migration-source");
const legacyFile = document.querySelector("#legacy-file");
const migrationPreview = document.querySelector("#migration-preview");
const migrationFields = document.querySelector("#migration-fields");
const previewFile = document.querySelector("#preview-file");
const previewSummary = document.querySelector("#preview-summary");
const setupFeedback = document.querySelector("#setup-feedback");
const skipImport = document.querySelector("#skip-import");
const cancelImport = document.querySelector("#cancel-import");
const applyImport = document.querySelector("#apply-import");
const startedAt = Date.now();
const stageOrder = ["preflight", "dependencies", "migration", "core", "interface"];
let setupRequired = false;

function render(snapshot) {
  if (setupRequired) return;
  stageElement.textContent = snapshot.title;
  messageElement.textContent = snapshot.message;
  errorCode.textContent = snapshot.error_code || "";
  errorActions.hidden = snapshot.state !== "blocked";

  const activeIndex = stageOrder.indexOf(snapshot.stage);
  for (const item of stageItems) {
    const index = stageOrder.indexOf(item.dataset.stage);
    item.classList.toggle("is-active", index === activeIndex);
    item.classList.toggle(
      "is-complete",
      activeIndex > index || ["ready", "degraded"].includes(snapshot.state),
    );
  }
}

function setSetupMode(required) {
  setupRequired = required;
  setupPanel.hidden = !required;
  statusCard.hidden = required;
  stageList.hidden = required;
  errorActions.hidden = true;
}

function showFeedback(message, isError = false) {
  setupFeedback.textContent = message;
  setupFeedback.classList.toggle("is-error", isError);
}

function setSetupBusy(busy) {
  legacyFile.disabled = busy;
  skipImport.disabled = busy;
  cancelImport.disabled = busy;
  applyImport.disabled = busy;
  setupPanel.setAttribute("aria-busy", String(busy));
}

function renderMigrationPreview(preview) {
  migrationFields.replaceChildren();
  previewFile.textContent = preview.sourceName;
  previewSummary.textContent = `${preview.fields.length} 项可导入 · ${preview.ignoredFields.length} 项由桌面版接管`;
  for (const field of preview.fields) {
    const label = document.createElement("label");
    label.className = "migration-field";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.name = "migration-field";
    checkbox.value = field.name;
    checkbox.checked = field.selectedByDefault;

    const name = document.createElement("span");
    name.className = "field-name";
    name.textContent = field.name;

    const target = document.createElement("span");
    target.className = "field-target";
    const destination = document.createElement("strong");
    destination.textContent = field.destination;
    const value = document.createElement("small");
    value.textContent = field.replacesExisting
      ? `${field.displayValue} · 将替换现有值`
      : field.displayValue;
    target.append(destination, value);
    label.append(checkbox, name, target);
    migrationFields.append(label);
  }
  migrationSource.hidden = true;
  migrationPreview.hidden = false;
  showFeedback("已生成预览，尚未写入任何配置。", false);
}

async function beginRuntime(message) {
  setSetupMode(false);
  stageElement.textContent = "正在应用桌面配置";
  messageElement.textContent = message;
  render(await invoke("runtime_start"));
}

async function refresh() {
  try {
    const config = await invoke("desktop_config_status");
    if (config?.firstRun) {
      setSetupMode(true);
      showFeedback("你可以导入旧配置，也可以直接使用全新配置。", false);
      return;
    }
    setSetupMode(false);
    render(await invoke("runtime_status"));
  } catch (error) {
    setSetupMode(false);
    render({
      state: "blocked",
      stage: "preflight",
      title: "无法读取桌面运行状态",
      message: String(error),
      error_code: "DESKTOP_STATUS_UNAVAILABLE",
    });
  }
}

legacyFile.addEventListener("change", async () => {
  const [file] = legacyFile.files || [];
  if (!file) return;
  if (file.size > 1024 * 1024) {
    showFeedback("配置文件超过 1 MiB，未读取。", true);
    legacyFile.value = "";
    return;
  }
  setSetupBusy(true);
  showFeedback("正在本地解析配置…", false);
  try {
    const contents = await file.text();
    renderMigrationPreview(
      await invoke("desktop_config_preview", {
        sourceName: file.name,
        contents,
      }),
    );
  } catch (error) {
    showFeedback(String(error), true);
  } finally {
    setSetupBusy(false);
  }
});

migrationPreview.addEventListener("submit", async (event) => {
  event.preventDefault();
  const selectedNames = [...migrationFields.querySelectorAll("input:checked")].map(
    (input) => input.value,
  );
  setSetupBusy(true);
  try {
    const result = await invoke("desktop_config_apply", { selectedNames });
    await beginRuntime(
      `已导入 ${result.importedFields} 项；密钥只保存在当前 Windows 用户的受保护存储中。`,
    );
  } catch (error) {
    showFeedback(String(error), true);
    setSetupBusy(false);
  }
});

cancelImport.addEventListener("click", async () => {
  setSetupBusy(true);
  try {
    await invoke("desktop_config_cancel");
    migrationPreview.hidden = true;
    migrationSource.hidden = false;
    migrationFields.replaceChildren();
    legacyFile.value = "";
    showFeedback("导入已取消；旧文件和桌面配置均未改变。", false);
  } catch (error) {
    showFeedback(String(error), true);
  } finally {
    setSetupBusy(false);
  }
});

skipImport.addEventListener("click", async () => {
  setSetupBusy(true);
  try {
    await invoke("desktop_config_complete");
    await beginRuntime("已创建全新桌面配置，后续可在设置中添加模型密钥。");
  } catch (error) {
    showFeedback(String(error), true);
    setSetupBusy(false);
  }
});

retryButton.addEventListener("click", async () => {
  retryButton.disabled = true;
  try {
    render(await invoke("runtime_start"));
  } finally {
    retryButton.disabled = false;
  }
});

setInterval(() => {
  const seconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
  elapsedElement.textContent = `已用时 ${seconds} 秒`;
}, 1000);

listen("runtime://snapshot", ({ payload }) => render(payload));
refresh();
