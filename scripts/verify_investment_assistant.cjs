const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const WebSocketClient = require("../apps/web/node_modules/next/dist/compiled/ws");

const baseUrl = "http://127.0.0.1:3000";
const apiUrl = "http://127.0.0.1:8000/api/v1";
const edgePath =
  process.env.JARVIS_EDGE_PATH ??
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const remotePort = 9340;
const marker = Date.now();
const symbol = `QA${String(marker).slice(-7)}`;
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

async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(
      `${options.method ?? "GET"} ${url}: ${response.status} ${body}`,
    );
  }
  return response.status === 204 ? null : response.json();
}

function jsonPost(url, body) {
  return request(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function clickText(selector, text) {
  return `(() => {
    const element = Array.from(document.querySelectorAll(${JSON.stringify(
      selector,
    )})).find((item) => item.textContent.includes(${JSON.stringify(text)}));
    if (!element) throw new Error(${JSON.stringify(`Missing ${text}`)});
    element.click();
    return true;
  })()`;
}

async function main() {
  const projectRoot = path.resolve(__dirname, "..");
  const positionsScreenshot = path.join(
    projectRoot,
    "artifacts",
    "investment-positions-verified.png",
  );
  const reviewScreenshot = path.join(
    projectRoot,
    "artifacts",
    "investment-review-verified.png",
  );
  const profileDirectory = fs.mkdtempSync(
    path.join(os.tmpdir(), "jarvis-edge-investment-qa-"),
  );
  let asset;
  let news;
  let client;
  let edge;
  const consoleErrors = [];
  const pageErrors = [];
  const failedRequests = [];
  const badResponses = [];

  try {
    asset = await jsonPost(`${apiUrl}/investment/assets`, {
      name: "Jarvis 验收资产",
      symbol,
      market: "QA",
      asset_type: "stock",
      currency: "CNY",
      latest_price: 12,
      latest_price_date: new Date().toISOString().slice(0, 10),
    });
    await jsonPost(`${apiUrl}/investment/positions`, {
      asset_id: asset.id,
      quantity: 100,
      average_cost: 10,
      fees: 5,
      transaction_date: new Date().toISOString().slice(0, 10),
      reason: "验证初始持仓、成本和长期投资理由",
      target_allocation: 20,
      risk_level: "medium",
    });
    await jsonPost(`${apiUrl}/investment/transactions`, {
      asset_id: asset.id,
      transaction_type: "dividend",
      transaction_date: new Date().toISOString().slice(0, 10),
      cash_amount: 30,
      fees: 1,
      reason: "验证分红记录",
    });
    await jsonPost(`${apiUrl}/investment/theses`, {
      asset_id: asset.id,
      title: "Jarvis 验收投资假设",
      original_reason: "验证初始持仓、成本和长期投资理由",
      key_assumptions: ["经营事实保持稳定"],
      watch_events: ["下一次经营更新"],
      invalidation_conditions: ["经营现金流明显恶化"],
      risk_level: "medium",
      cloud_allowed: false,
    });
    news = await jsonPost(`${apiUrl}/intelligence/items/manual`, {
      title: `[验收] ${symbol} 发布经营更新`,
      url: `https://example.com/jarvis-investment-qa-${marker}`,
      source_name: "Jarvis 投资验收来源",
      source_excerpt: "这是一条用于验证持仓和情报关联的事实。",
      category: "investment",
      language: "zh-CN",
    });
    await jsonPost(
      `${apiUrl}/investment/assets/${asset.id}/news/${news.id}`,
      { relationship_note: "验证情报进入投资复盘" },
    );
    await jsonPost(`${apiUrl}/investment/reviews/generate`, {
      asset_id: asset.id,
      review_type: "weekly",
    });

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
        "--window-size=1440,1150",
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

    await client.navigate(`${baseUrl}/investment`);
    await client.waitFor(
      `Array.from(document.querySelectorAll(".position-card")).some((card) => card.textContent.includes(${JSON.stringify(symbol)}))`,
    );
    const positionAudit = await client.evaluate(`(() => {
      const card = Array.from(document.querySelectorAll(".position-card"))
        .find((item) => item.textContent.includes(${JSON.stringify(symbol)}));
      return {
        title: document.querySelector("h1")?.textContent?.replace(/\\s+/g, " ").trim(),
        cardText: card?.textContent?.replace(/\\s+/g, " ").trim(),
        stats: Array.from(document.querySelectorAll(".investment-stats strong"))
          .map((item) => item.textContent),
      };
    })()`);
    if (
      !positionAudit.title.includes("Jarvis 投资助手") ||
      !positionAudit.cardText.includes("1,200 CNY") ||
      !positionAudit.cardText.includes("29")
    ) {
      throw new Error(`Position audit failed: ${JSON.stringify(positionAudit)}`);
    }
    await client.screenshot(positionsScreenshot);

    await client.evaluate(clickText(".investment-tabs button", "交易"));
    await client.waitFor(
      `Array.from(document.querySelectorAll(".transaction-table tr")).some((row) => row.textContent.includes(${JSON.stringify(symbol)}))`,
    );
    await client.evaluate(clickText(".investment-tabs button", "投资理由"));
    await client.waitFor(
      `document.body.textContent.includes("Jarvis 验收投资假设")`,
    );
    await client.evaluate(clickText(".investment-tabs button", "关联情报"));
    await client.waitFor(
      `document.body.textContent.includes(${JSON.stringify(news.title)})`,
    );
    await client.evaluate(clickText(".investment-tabs button", "复盘"));
    await client.waitFor(
      `Array.from(document.querySelectorAll(".review-card")).some((card) => card.textContent.includes(${JSON.stringify(symbol)}))`,
    );
    const reviewAudit = await client.evaluate(`(() => {
      const card = Array.from(document.querySelectorAll(".review-card"))
        .find((item) => item.textContent.includes(${JSON.stringify(symbol)}));
      return {
        hasReason: card?.textContent.includes("验证初始持仓、成本和长期投资理由"),
        hasDisclaimer: card?.textContent.includes("不构成投资建议"),
        status: card?.querySelector("i")?.textContent,
      };
    })()`);
    if (!reviewAudit.hasReason || !reviewAudit.hasDisclaimer) {
      throw new Error(`Review audit failed: ${JSON.stringify(reviewAudit)}`);
    }
    await client.screenshot(reviewScreenshot);

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
          positionAudit,
          reviewAudit,
          consoleErrors: consoleErrors.length,
          pageErrors: pageErrors.length,
          failedRequests: failedRequests.length,
          badResponses: badResponses.length,
          screenshots: [positionsScreenshot, reviewScreenshot],
        },
        null,
        2,
      ),
    );
  } finally {
    try {
      if (asset?.id) {
        await request(`${apiUrl}/investment/assets/${asset.id}`, {
          method: "DELETE",
        });
      }
      if (news?.id) {
        await request(`${apiUrl}/intelligence/items/${news.id}`, {
          method: "DELETE",
        });
      }
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
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
