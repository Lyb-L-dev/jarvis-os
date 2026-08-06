const { chromium } = require("../apps/web/node_modules/playwright");
const path = require("node:path");

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath:
      process.env.JARVIS_EDGE_PATH ??
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  });
  const errors = [];
  const failedRequests = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1500, height: 1200 } });
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });
    page.on("requestfailed", (request) => {
      failedRequests.push(
        `${request.method()} ${request.url()} ${request.failure()?.errorText ?? ""}`,
      );
    });

    await page.goto("http://127.0.0.1:3000/evaluation", {
      waitUntil: "networkidle",
    });
    const panel = page.locator(".memory-shadow-lab");
    await panel.waitFor({ state: "visible", timeout: 20_000 });
    await panel.getByText("本地隔离已就绪").waitFor({ timeout: 20_000 });
    await panel.getByText("已达到").waitFor({ timeout: 20_000 });
    const result = {
      heading: await panel.locator("h3").first().innerText(),
      ready: await panel.getByText("本地隔离已就绪").isVisible(),
      gate: await panel.getByText("已达到").isVisible(),
      noCloud: await panel.getByText("云模型 未使用").isVisible(),
      telemetryOff: await panel.getByText("遥测 已关闭").isVisible(),
      formalWritesAbsent: await panel.getByText("正式记忆写入 不存在").isVisible(),
      runButtons: await panel.getByRole("button", { name: "运行三引擎对比" }).count(),
      resultCards: await panel.locator(".memory-shadow-run").count(),
      errors,
      failedRequests,
    };
    await page.screenshot({
      path: path.resolve(
        __dirname,
        "..",
        "artifacts",
        "memory-shadow-sprint28-evaluation.png",
      ),
      fullPage: true,
    });
    console.log(JSON.stringify(result, null, 2));
    if (
      !result.ready ||
      !result.gate ||
      !result.noCloud ||
      !result.telemetryOff ||
      !result.formalWritesAbsent ||
      result.runButtons !== 10 ||
      result.resultCards < 10 ||
      errors.length ||
      failedRequests.length
    ) {
      process.exitCode = 1;
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
