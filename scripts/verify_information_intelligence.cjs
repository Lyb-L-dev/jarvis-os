const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const WebSocketClient = require("../apps/web/node_modules/next/dist/compiled/ws");

const baseUrl = "http://127.0.0.1:3000";
const apiUrl = "http://127.0.0.1:8000/api/v1";
const testTitle = `[验收] Jarvis 情报交互 ${Date.now()}`;
const testUrl = `https://example.com/jarvis-intelligence-qa-${Date.now()}`;
const edgePath =
  process.env.JARVIS_EDGE_PATH ??
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const remotePort = 9338;
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
    this.socket.on("message", async (messageData) => {
      let rawMessage = messageData;
      if (rawMessage instanceof ArrayBuffer) {
        rawMessage = Buffer.from(rawMessage).toString("utf8");
      } else if (ArrayBuffer.isView(rawMessage)) {
        rawMessage = Buffer.from(
          rawMessage.buffer,
          rawMessage.byteOffset,
          rawMessage.byteLength,
        ).toString("utf8");
      } else if (
        typeof rawMessage !== "string" &&
        typeof rawMessage?.text === "function"
      ) {
        rawMessage = await rawMessage.text();
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
    await delay(1_200);
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

async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok && response.status !== 404) {
    const body = await response.text();
    throw new Error(`${options.method ?? "GET"} ${url}: ${response.status} ${body}`);
  }
  return response.status === 204 ? null : response.json();
}

function textSelector(selector, text) {
  return `Array.from(document.querySelectorAll(${JSON.stringify(
    selector,
  )})).find((element) => element.textContent.includes(${JSON.stringify(text)}))`;
}

function clickText(selector, text) {
  return `(() => {
    const element = ${textSelector(selector, text)};
    if (!element) throw new Error(${JSON.stringify(
      `Element not found: ${selector} ${text}`,
    )});
    element.click();
    return true;
  })()`;
}

function fill(selector, value) {
  return `(() => {
    const element = document.querySelector(${JSON.stringify(selector)});
    if (!element) throw new Error(${JSON.stringify(`Element not found: ${selector}`)});
    const setter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value"
    ).set;
    setter.call(element, ${JSON.stringify(value)});
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    return element.value;
  })()`;
}

async function main() {
  const projectRoot = path.resolve(__dirname, "..");
  const briefScreenshot = path.join(
    projectRoot,
    "artifacts",
    "intelligence-brief-verified.png",
  );
  const sourcesScreenshot = path.join(
    projectRoot,
    "artifacts",
    "intelligence-sources-verified.png",
  );
  const profileDirectory = fs.mkdtempSync(
    path.join(os.tmpdir(), "jarvis-edge-intelligence-qa-"),
  );
  const originalOverview = await request(`${apiUrl}/intelligence/overview`);
  const testItem = await request(`${apiUrl}/intelligence/items/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: testTitle,
      url: testUrl,
      source_name: "Jarvis 验收来源",
      source_excerpt:
        "这是用于验证收藏、兴趣反馈和一键转任务的来源事实，验收结束后会清理。",
      category: "technology",
      language: "zh-CN",
    }),
  });
  let createdTaskId = null;
  const edge = spawn(
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
  let client;
  const consoleErrors = [];
  const pageErrors = [];
  const failedRequests = [];
  const badResponses = [];

  try {
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

    await client.navigate(`${baseUrl}/intelligence`);
    await client.waitFor(
      `document.querySelectorAll(".intel-card").length === 5`,
    );
    const briefAudit = await client.evaluate(`(() => {
      const cards = Array.from(document.querySelectorAll(".intel-card"));
      return {
        title: document.querySelector("h1")?.textContent,
        cardCount: cards.length,
        fullyLayered: cards.every((card) =>
          card.querySelector(".intel-fact-block") &&
          card.querySelector(".intel-interpretation-grid") &&
          card.querySelector(".intel-action-block") &&
          card.querySelector('a[target="_blank"]')
        ),
        providerText: document.querySelector(".intel-brief-audit")?.textContent,
      };
    })()`);
    if (
      briefAudit.title !== "情报中心" ||
      briefAudit.cardCount !== 5 ||
      !briefAudit.fullyLayered
    ) {
      throw new Error(`Brief audit failed: ${JSON.stringify(briefAudit)}`);
    }
    await client.screenshot(briefScreenshot);

    await client.evaluate(clickText(".intel-tabs button", "信息流"));
    await client.waitFor(`document.querySelector(".intel-toolbar input")`);
    await client.evaluate(fill(".intel-toolbar input", testTitle));
    await client.waitFor(
      `${textSelector(".intel-card", testTitle)} !== undefined`,
    );
    await client.evaluate(`(() => {
      const card = ${textSelector(".intel-card", testTitle)};
      const button = Array.from(card.querySelectorAll("button"))
        .find((item) => item.textContent.includes("收藏"));
      button.click();
      return true;
    })()`);
    await client.waitFor(
      `${textSelector(".intel-card", testTitle)}?.textContent.includes("已收藏")`,
    );
    await client.evaluate(`(() => {
      const card = ${textSelector(".intel-card", testTitle)};
      const button = Array.from(card.querySelectorAll("button"))
        .find((item) => item.textContent.includes("转为任务"));
      button.click();
      return true;
    })()`);
    await client.waitFor(
      `${textSelector(".intel-card", testTitle)}?.textContent.includes("已转任务")`,
    );
    const tasks = await request(`${apiUrl}/tasks`);
    const createdTask = tasks.find(
      (item) =>
        item.source_type === "intelligence" &&
        item.title.includes(testTitle),
    );
    if (!createdTask) throw new Error("Converted task was not persisted.");
    createdTaskId = createdTask.id;

    await client.evaluate(clickText(".intel-tabs button", "来源与偏好"));
    await client.waitFor(
      `document.querySelectorAll(".intel-source-list > article").length === 6`,
    );
    const sourceAudit = await client.evaluate(`(() => {
      const rows = Array.from(
        document.querySelectorAll(".intel-source-list > article")
      );
      return {
        count: rows.length,
        healthy: rows.every((row) =>
          row.querySelector(".intel-source-state")?.textContent.includes("正常")
        ),
        names: rows.map((row) => row.querySelector("h3")?.textContent),
      };
    })()`);
    if (sourceAudit.count !== 6 || !sourceAudit.healthy) {
      throw new Error(`Source audit failed: ${JSON.stringify(sourceAudit)}`);
    }
    await client.screenshot(sourcesScreenshot);

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
          briefAudit,
          sourceAudit,
          interaction: {
            saved: true,
            taskCreated: true,
          },
          consoleErrors: consoleErrors.length,
          pageErrors: pageErrors.length,
          failedRequests: failedRequests.length,
          badResponses: badResponses.length,
          screenshots: [briefScreenshot, sourcesScreenshot],
        },
        null,
        2,
      ),
    );
  } finally {
    try {
      if (createdTaskId) {
        await request(`${apiUrl}/tasks/${createdTaskId}`, { method: "DELETE" });
      }
      if (testItem?.id) {
        await request(`${apiUrl}/intelligence/items/${testItem.id}`, {
          method: "DELETE",
        });
      }
      await request(`${apiUrl}/intelligence/preferences`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(originalOverview.interests),
      });
    } finally {
      client?.close();
      edge.kill();
      await Promise.race([
        new Promise((resolve) => edge.once("exit", resolve)),
        delay(2_000),
      ]);
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
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
