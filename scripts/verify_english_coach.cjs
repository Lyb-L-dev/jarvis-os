const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const WebSocketClient = require("../apps/web/node_modules/next/dist/compiled/ws");

const baseUrl = "http://127.0.0.1:3000";
const apiUrl = "http://127.0.0.1:8000/api/v1";
const topic = "[验收] English Coach";
const learnerSentence = "I go to school yesterday.";
const learnerSentenceSearch = "I go to school yesterday";
const edgePath =
  process.env.JARVIS_EDGE_PATH ??
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const remotePort = 9337;

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
        () => reject(new Error("Timed out opening the DevTools WebSocket.")),
        5_000,
      );
      this.socket.once(
        "open",
        () => {
          clearTimeout(timer);
          resolve();
        },
      );
      this.socket.once(
        "error",
        (error) => {
          clearTimeout(timer);
          reject(error);
        },
      );
    });
    this.socket.on("close", (code, reason) => {
      if (process.env.JARVIS_CDP_DEBUG === "1") {
        console.error("CDP closed", code, reason.toString());
      }
    });
    this.socket.on("error", (error) => {
      if (process.env.JARVIS_CDP_DEBUG === "1") {
        console.error("CDP socket error", error);
      }
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
      if (process.env.JARVIS_CDP_DEBUG === "1") {
        console.error("CDP message", String(rawMessage).slice(0, 200));
      }
      const message = JSON.parse(rawMessage);
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
        reject(new Error(`Timed out running DevTools command: ${method}`));
      }, 10_000);
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
    const current = this.listeners.get(method) ?? [];
    current.push(listener);
    this.listeners.set(method, current);
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

  async reload() {
    const loaded = this.once("Page.loadEventFired");
    await this.command("Page.reload", { ignoreCache: true });
    await loaded;
    await delay(1_200);
  }

  async waitFor(expression, timeout = 15_000) {
    const started = Date.now();
    while (Date.now() - started < timeout) {
      if (await this.evaluate(`Boolean(${expression})`)) return;
      await delay(200);
    }
    throw new Error(`Timed out waiting for: ${expression}`);
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

async function apiRequest(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok && response.status !== 404) {
    throw new Error(`${options.method ?? "GET"} ${url}: ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

async function cleanup() {
  const sessions = await apiRequest(`${apiUrl}/english/sessions`);
  for (const session of sessions.filter((item) => item.topic === topic)) {
    await apiRequest(`${apiUrl}/english/sessions/${session.id}`, {
      method: "DELETE",
    });
  }
  const mistakes = await apiRequest(
    `${apiUrl}/english/mistakes?q=${encodeURIComponent(learnerSentenceSearch)}`,
  );
  for (const mistake of mistakes) {
    await apiRequest(`${apiUrl}/english/mistakes/${mistake.id}`, {
      method: "DELETE",
    });
  }
  const notifications = await apiRequest(`${apiUrl}/notifications`);
  for (const notification of notifications.filter(
    (item) =>
      item.category === "english_review" &&
      item.message.includes(learnerSentenceSearch),
  )) {
    await apiRequest(`${apiUrl}/notifications/${notification.id}`, {
      method: "DELETE",
    });
  }
}

function textSelector(selector, text) {
  return `Array.from(document.querySelectorAll(${JSON.stringify(
    selector,
  )})).find((element) => element.textContent.includes(${JSON.stringify(text)}))`;
}

function clickExpression(selector, text) {
  return `(() => { const element = ${textSelector(
    selector,
    text,
  )}; if (!element) throw new Error(${JSON.stringify(
    `Element not found: ${selector} ${text}`,
  )}); element.click(); return true; })()`;
}

function fillExpression(selector, value) {
  return `(() => {
    const element = document.querySelector(${JSON.stringify(selector)});
    if (!element) throw new Error(${JSON.stringify(`Element not found: ${selector}`)});
    const prototype = element.tagName === "TEXTAREA"
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, "value").set.call(
      element,
      ${JSON.stringify(value)}
    );
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    return element.value;
  })()`;
}

async function main() {
  const projectRoot = path.resolve(__dirname, "..");
  const conversationScreenshot = path.join(
    projectRoot,
    "artifacts",
    "english-coach-verified.png",
  );
  const reviewScreenshot = path.join(
    projectRoot,
    "artifacts",
    "english-review-verified.png",
  );
  const profileDirectory = fs.mkdtempSync(
    path.join(os.tmpdir(), "jarvis-edge-english-qa-"),
  );
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
      "--window-size=1440,1050",
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe"], windowsHide: true },
  );
  if (process.env.JARVIS_CDP_DEBUG === "1") {
    edge.on("exit", (code, signal) =>
      console.error("Edge exited", code, signal),
    );
    edge.stderr.on("data", (data) =>
      console.error("Edge stderr", data.toString()),
    );
  }
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
        // Edge is still starting.
      }
      await delay(200);
    }
    if (!target) throw new Error("Headless Edge did not expose a page target.");

    client = new CdpClient(target.webSocketDebuggerUrl);
    await client.connect();
    await Promise.all([
      client.command("Page.enable"),
      client.command("Runtime.enable"),
      client.command("Network.enable"),
      client.command("Emulation.setDeviceMetricsOverride", {
        width: 1440,
        height: 1050,
        deviceScaleFactor: 1,
        mobile: false,
      }),
    ]);
    client.on("Runtime.consoleAPICalled", ({ type, args }) => {
      if (type === "error") {
        consoleErrors.push(
          args.map((argument) => argument.value ?? argument.description).join(" "),
        );
      }
    });
    client.on("Runtime.exceptionThrown", ({ exceptionDetails }) => {
      pageErrors.push(
        exceptionDetails.exception?.description ?? exceptionDetails.text,
      );
    });
    client.on("Network.loadingFailed", ({ errorText, canceled }) => {
      if (!canceled && errorText !== "net::ERR_ABORTED") {
        failedRequests.push(errorText);
      }
    });
    client.on("Network.responseReceived", ({ response }) => {
      if (response.status >= 400) {
        badResponses.push(`${response.status} ${response.url}`);
      }
    });

    await client.navigate(`${baseUrl}/english`);
    await client.waitFor('document.querySelector(".english-page")');
    await cleanup();
    await client.reload();

    await client.evaluate(clickExpression("button", "新练习"));
    await client.waitFor('document.querySelector(".english-setup")');
    await client.evaluate(
      clickExpression(".english-option-grid label", "主题练习"),
    );
    await client.waitFor(
      'document.querySelector(\'input[placeholder="例如：My weekend plan"]\')',
    );
    await client.evaluate(
      fillExpression(
        'input[placeholder="例如：My weekend plan"]',
        topic,
      ),
    );
    await client.evaluate(
      clickExpression(".english-correction-options label", "温和纠错"),
    );
    await client.evaluate(clickExpression("button", "开始英语对话"));
    await client.waitFor(
      `document.querySelector(".english-conversation-head h2")?.textContent.includes(${JSON.stringify(
        topic,
      )})`,
      15_000,
    );

    await client.evaluate(
      fillExpression(
        'textarea[placeholder="Write or speak in English…"]',
        learnerSentence,
      ),
    );
    await client.waitFor(
      `Array.from(document.querySelectorAll("button")).some(
        (element) => element.textContent.trim() === "发送" && !element.disabled
      )`,
    );
    await client.evaluate(clickExpression("button", "发送"));
    await client.waitFor(
      `${textSelector(
        ".english-inline-correction",
        "I went to school yesterday",
      )}`,
      120_000,
    );
    const localProviderVisible = await client.evaluate(
      `Boolean(${textSelector(".english-message-label small", "本地 Qwen")})`,
    );
    await client.screenshot(conversationScreenshot);

    await client.evaluate(`(() => {
      const card = ${textSelector(
        ".english-inline-correction",
        "I went to school yesterday",
      )};
      const button = Array.from(card.querySelectorAll("button")).find(
        (element) => element.textContent.includes("确认并加入复习")
      );
      button.click();
      return true;
    })()`);
    await client.waitFor(
      `${textSelector(
        ".english-feedback",
        "明晚 19:00 会通过桌面和语音提醒你",
      )}`,
    );
    await client.evaluate(clickExpression("button", "结束并总结"));
    await client.waitFor(
      `${textSelector(".english-session-summary", "本次学习小结")}`,
      30_000,
    );

    const matchingMistakes = await apiRequest(
      `${apiUrl}/english/mistakes?q=${encodeURIComponent(
        learnerSentenceSearch,
      )}`,
    );
    if (matchingMistakes.length !== 1) {
      throw new Error(
        `Expected one aggregated mistake, got ${matchingMistakes.length}`,
      );
    }
    await apiRequest(
      `${apiUrl}/english/mistakes/${matchingMistakes[0].id}/confirm`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          review_at: new Date(Date.now() - 1_000).toISOString(),
        }),
      },
    );

    await client.reload();
    await client.evaluate(clickExpression(".english-tabs button", "今日复习"));
    await client.waitFor(
      `${textSelector(".english-review-card", learnerSentenceSearch)}`,
    );
    await client.evaluate(
      fillExpression(
        '.english-review-card textarea[placeholder="在这里写出你认为正确的句子…"]',
        "I went to school yesterday.",
      ),
    );
    await client.evaluate(`(() => {
      const card = ${textSelector(".english-review-card", learnerSentenceSearch)};
      const button = Array.from(card.querySelectorAll("button")).find(
        (element) => element.textContent.includes("核对答案")
      );
      button.click();
      return true;
    })()`);
    await client.waitFor(
      `${textSelector(".english-review-answer", "I went to school yesterday")}`,
    );
    await client.screenshot(reviewScreenshot);
    await client.evaluate(`(() => {
      const card = ${textSelector(".english-review-card", learnerSentenceSearch)};
      const button = Array.from(card.querySelectorAll("button")).find(
        (element) => element.textContent.trim() === "记住了"
      );
      button.click();
      return true;
    })()`);
    await client.waitFor(
      `${textSelector(
        ".english-feedback",
        "复习结果已保存，下次时间已自动安排",
      )}`,
    );

    const upcoming = await apiRequest(`${apiUrl}/english/reviews/upcoming`);
    const notifications = await apiRequest(`${apiUrl}/notifications`);
    const reminder = notifications.find(
      (item) =>
        item.category === "english_review" &&
        item.message.includes(learnerSentenceSearch) &&
        item.status === "pending",
    );
    await cleanup();

    const result = {
      sessionCreated: true,
      standardRouteUsed: localProviderVisible,
      deterministicCorrectionVisible: true,
      userConfirmationRequired: true,
      sessionSummaryVisible: true,
      dueReviewCompleted: true,
      nextReviewScheduled: upcoming.length > 0,
      desktopAndVoiceReminder:
        reminder?.requested_channels?.join(",") === "desktop,voice",
      cleanupComplete: true,
      screenshots: [conversationScreenshot, reviewScreenshot],
      consoleErrors,
      pageErrors,
      failedRequests,
      badResponses,
    };
    console.log(JSON.stringify(result, null, 2));
    if (
      !result.standardRouteUsed ||
      !result.nextReviewScheduled ||
      !result.desktopAndVoiceReminder ||
      consoleErrors.length ||
      pageErrors.length ||
      failedRequests.length ||
      badResponses.length
    ) {
      process.exitCode = 1;
    }
  } catch (error) {
    if (client) {
      const pageText = await client
        .evaluate("document.body?.innerText ?? ''")
        .catch(() => "");
      console.error("Page state at failure:\n", pageText.slice(-3_000));
      await client
        .screenshot(
          path.join(projectRoot, "artifacts", "english-qa-failure.png"),
        )
        .catch(() => {});
    }
    throw error;
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

main().catch(async (error) => {
  console.error(error);
  try {
    await cleanup();
  } catch {
    // Preserve the original validation error.
  }
  process.exitCode = 1;
});
