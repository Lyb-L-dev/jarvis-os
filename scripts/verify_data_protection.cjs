const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const WebSocketClient = require("../apps/web/node_modules/next/dist/compiled/ws");

const baseUrl = "http://127.0.0.1:3000";
const edgePath =
  process.env.JARVIS_EDGE_PATH ??
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const remotePort = 9341;
const delay = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

class CdpClient {
  constructor(webSocketUrl) {
    this.webSocketUrl = webSocketUrl;
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
  }

  async connect() {
    this.socket = new WebSocketClient(this.webSocketUrl);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error("Timed out opening DevTools.")),
        5_000,
      );
      this.socket.once("open", () => {
        clearTimeout(timer);
        resolve();
      });
      this.socket.once("error", reject);
    });
    this.socket.on("message", (messageData) => {
      let rawMessage = messageData;
      if (rawMessage instanceof ArrayBuffer) {
        rawMessage = Buffer.from(rawMessage).toString("utf8");
      } else if (ArrayBuffer.isView(rawMessage)) {
        rawMessage = Buffer.from(
          rawMessage.buffer,
          rawMessage.byteOffset,
          rawMessage.byteLength,
        ).toString("utf8");
      }
      const message = JSON.parse(String(rawMessage));
      if (message.id) {
        const request = this.pending.get(message.id);
        if (!request) return;
        this.pending.delete(message.id);
        if (message.error) request.reject(new Error(message.error.message));
        else request.resolve(message.result);
        return;
      }
      for (const listener of this.listeners.get(message.method) ?? []) {
        listener(message.params ?? {});
      }
    });
  }

  command(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Timed out: ${method}`));
      }, 15_000);
      this.pending.set(id, {
        resolve: (value) => {
          clearTimeout(timer);
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timer);
          reject(error);
        },
      });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  on(method, listener) {
    const listeners = this.listeners.get(method) ?? [];
    listeners.push(listener);
    this.listeners.set(method, listeners);
  }

  once(method, timeout = 30_000) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error(`Timed out waiting for ${method}`)),
        timeout,
      );
      const listener = (params) => {
        clearTimeout(timer);
        this.listeners.set(
          method,
          (this.listeners.get(method) ?? []).filter(
            (candidate) => candidate !== listener,
          ),
        );
        resolve(params);
      };
      this.on(method, listener);
    });
  }

  async evaluate(expression) {
    const result = await this.command("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (result.exceptionDetails) {
      throw new Error(
        result.exceptionDetails.exception?.description ??
          result.exceptionDetails.text,
      );
    }
    return result.result.value;
  }

  async navigate(url) {
    const loaded = this.once("Page.loadEventFired");
    await this.command("Page.navigate", { url });
    await loaded;
    await delay(1_000);
  }

  async waitFor(expression, timeout = 20_000) {
    const started = Date.now();
    while (Date.now() - started < timeout) {
      if (await this.evaluate(`Boolean(${expression})`)) return;
      await delay(200);
    }
    throw new Error(`Timed out waiting for ${expression}`);
  }

  async screenshot(filePath) {
    const result = await this.command("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: true,
    });
    fs.writeFileSync(filePath, Buffer.from(result.data, "base64"));
  }

  close() {
    this.socket?.close();
  }
}

async function main() {
  const projectRoot = path.resolve(__dirname, "..");
  const screenshotPath = path.join(
    projectRoot,
    "artifacts",
    "data-protection-verified.png",
  );
  const profileDirectory = fs.mkdtempSync(
    path.join(os.tmpdir(), "jarvis-edge-backup-qa-"),
  );
  let client;
  let edge;
  const consoleErrors = [];
  const pageErrors = [];
  const failedRequests = [];
  const badResponses = [];

  try {
    edge = spawn(
      edgePath,
      [
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-allow-origins=*",
        `--remote-debugging-port=${remotePort}`,
        `--user-data-dir=${profileDirectory}`,
        "--window-size=1440,1100",
        "about:blank",
      ],
      { stdio: ["ignore", "ignore", "ignore"], windowsHide: true },
    );
    let target;
    for (let attempt = 0; attempt < 50; attempt += 1) {
      try {
        const targets = await fetch(
          `http://127.0.0.1:${remotePort}/json/list`,
        ).then((response) => response.json());
        target = targets.find((item) => item.type === "page");
        if (target) break;
      } catch {
        // Edge is starting.
      }
      await delay(200);
    }
    if (!target) throw new Error("Headless Edge did not expose a page target.");

    client = new CdpClient(target.webSocketDebuggerUrl);
    await client.connect();
    await client.command("Page.enable");
    await client.command("Runtime.enable");
    await client.command("Network.enable");
    client.on("Runtime.consoleAPICalled", ({ type, args }) => {
      if (type === "error" || type === "warning") {
        consoleErrors.push(
          `${type}: ${args.map((item) => item.value ?? item.description).join(" ")}`,
        );
      }
    });
    client.on("Runtime.exceptionThrown", ({ exceptionDetails }) => {
      pageErrors.push(
        exceptionDetails.exception?.description ?? exceptionDetails.text,
      );
    });
    client.on("Network.loadingFailed", ({ canceled, errorText, requestId }) => {
      if (!canceled && errorText !== "net::ERR_ABORTED") {
        failedRequests.push(`${requestId}: ${errorText}`);
      }
    });
    client.on("Network.responseReceived", ({ response }) => {
      if (response.status >= 400) {
        badResponses.push(`${response.status} ${response.url}`);
      }
    });

    await client.navigate(`${baseUrl}/settings`);
    await client.waitFor(
      `document.querySelector(".backup-center")?.textContent.includes("恢复验证通过")`,
    );
    await client.waitFor(
      `document.querySelector(".system-status-line")?.textContent.includes("已就绪")`,
    );
    const audit = await client.evaluate(`(() => {
      const center = document.querySelector(".backup-center");
      return {
        title: document.querySelector("h1")?.textContent?.replace(/\\s+/g, " ").trim(),
        automaticBackupEnabled:
          center?.textContent.includes("自动备份") &&
          center?.textContent.includes("已启用"),
        restoreVerified:
          center?.textContent.includes("恢复验证") &&
          center?.textContent.includes("已通过") &&
          center?.textContent.includes("恢复验证通过 · 35 张表"),
        backupLocation: center?.querySelector(".backup-location code")?.textContent,
        recoveryPointCount: center?.querySelector(".backup-list-heading > span")?.textContent,
        hasRestoreBoundary: center?.textContent.includes("网页不提供“覆盖恢复”按钮"),
      };
    })()`);
    if (
      !audit.automaticBackupEnabled ||
      !audit.restoreVerified ||
      audit.backupLocation !== `${projectRoot}\\backups` ||
      !audit.hasRestoreBoundary
    ) {
      throw new Error(`Data protection audit failed: ${JSON.stringify(audit)}`);
    }
    await client.evaluate(`(() => {
      const button = Array.from(document.querySelectorAll(".backup-actions button"))
        .find((item) => item.textContent.includes("导出个人数据"));
      if (!button) throw new Error("Missing personal data export button.");
      button.click();
      return true;
    })()`);
    await client.waitFor(
      `document.querySelector(".backup-notice.success")?.textContent.includes("个人数据已导出")`,
    );
    audit.dataExportTriggered = true;
    await client.screenshot(screenshotPath);

    if (
      consoleErrors.length ||
      pageErrors.length ||
      failedRequests.length ||
      badResponses.length
    ) {
      throw new Error(
        JSON.stringify({
          consoleErrors,
          pageErrors,
          failedRequests,
          badResponses,
        }),
      );
    }
    console.log(
      JSON.stringify(
        {
          audit,
          consoleErrors: consoleErrors.length,
          pageErrors: pageErrors.length,
          failedRequests: failedRequests.length,
          badResponses: badResponses.length,
          screenshot: screenshotPath,
        },
        null,
        2,
      ),
    );
  } finally {
    client?.close();
    edge?.kill();
    await delay(600);
    for (let attempt = 0; attempt < 5; attempt += 1) {
      try {
        fs.rmSync(profileDirectory, { recursive: true, force: true });
        break;
      } catch (error) {
        if (attempt === 4 && error.code !== "EBUSY") throw error;
        await delay(400);
      }
    }
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
